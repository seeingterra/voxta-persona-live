using System.Diagnostics;
using System.Collections.Concurrent;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Reflection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Voxta.Modules.LiveView;

public sealed class RendererHost : IAsyncDisposable
{
    private readonly SemaphoreSlim gate=new(1,1);
    private readonly ILogger<RendererHost> logger;
    private readonly CancellationTokenRegistration shutdown;
    private Process? process;
    private LiveViewSettings? settings;
    private readonly ConcurrentDictionary<Guid,byte> sessions=new();
    public string Root { get; init; } = AppContext.BaseDirectory;
    public string ContentRoot => Path.Combine(Root,"Data","LiveView");
    public string Token { get; } = Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
    public bool Enabled => settings!=null;
    public bool IsPrepared => File.Exists(Path.Combine(Root,"Data","Python","modules","PersonaLiveView","bootstrap.json"));
    public string Origin => settings?.VoxtaUrl.TrimEnd('/') ?? "http://localhost:5384";
    public int Port => settings?.Port ?? 8766;
    public RendererHost(IHostApplicationLifetime lifetime, ILogger<RendererHost> log)
    {
        logger=log;
        shutdown=lifetime.ApplicationStopping.Register(Kill);
    }
    public void Configure(LiveViewSettings value)
    {
        if(!Uri.TryCreate(value.VoxtaUrl,UriKind.Absolute,out var url) || url.Scheme!="http" || !url.IsLoopback || url.AbsolutePath!="/" || !string.IsNullOrEmpty(url.UserInfo) || !string.IsNullOrEmpty(url.Query))
            throw new ArgumentException("Use the local HTTP Voxta address.");
        if(value.Port is <1024 or >65535 || value.Fps is <1 or >30)throw new ArgumentException("Invalid renderer limits.");
        if(value.Device!="auto" && value.Device!="cpu" && !value.Device.StartsWith("GPU-",StringComparison.Ordinal))throw new ArgumentException("Use auto, cpu, or a GPU UUID.");
        settings=value;
    }
    public bool HasSession(Guid id) => Enabled && sessions.ContainsKey(id);
    public void AddSession(Guid id) => sessions.TryAdd(id,0);
    public async ValueTask RemoveSessionAsync(Guid id)
    {
        await gate.WaitAsync();
        try { sessions.TryRemove(id,out _); if(sessions.IsEmpty) Kill(); }
        finally { gate.Release(); }
    }
    public async Task EnsureStartedAsync(CancellationToken cancellation)
    {
        await gate.WaitAsync(cancellation);
        try
        {
            var config=settings ?? throw new InvalidOperationException("Enable Persona Live View in Voxta Services.");
            if(sessions.IsEmpty)throw new InvalidOperationException("Select Live view in chat augmentations and start the chat. If Voxta cannot start it, resolve the chat error first.");
            if(process is {HasExited:false})return;
            var python=ResolvePython();
            if(!File.Exists(python))throw new FileNotFoundException("Voxta's managed Python was not found. Reinstall or repair Voxta, then restart Persona Live View.");
            await ExtractRuntimePayloadAsync(cancellation);
            await PrepareRuntimeAsync(python,cancellation);
            // Refuse to adopt or terminate an unrelated listener.
            var probe=new TcpListener(IPAddress.Loopback,config.Port);
            try { probe.Start(); } finally { probe.Stop(); }
            var info=new ProcessStartInfo(python) { WorkingDirectory=ContentRoot, UseShellExecute=false, CreateNoWindow=true, RedirectStandardError=true, RedirectStandardOutput=true };
            info.Environment.Remove("PYTHONHOME");
            info.Environment.Remove("PYTHONPATH");
            foreach(var arg in new[]{"-m","uvicorn","backend.live_module:app","--host","127.0.0.1","--port",config.Port.ToString(),"--no-access-log"})info.ArgumentList.Add(arg);
            info.Environment["PERSONA_MODULE_TOKEN"]=Token;
            info.Environment["PERSONA_DATA"]=Path.Combine(ContentRoot,"data");
            info.Environment["PERSONA_VISUAL_PYTHON"]=python;
            info.Environment["PERSONA_VOXTA_URL"]=config.VoxtaUrl.TrimEnd('/');
            info.Environment["PERSONA_LIVE_DEVICE"]=config.Device;
            info.Environment["PERSONA_LIVE_FPS"]=config.Fps.ToString();
            info.Environment["PYTHONIOENCODING"]="utf-8";
            info.Environment["PERSONA_PARENT_PID"]=Environment.ProcessId.ToString();
            info.Environment["PYTHONPATH"]=Path.Combine(Root,"Data","Python","modules","PersonaLiveView","site-packages");
            process=Process.Start(info) ?? throw new InvalidOperationException("Renderer could not start.");
            var logPath=Path.Combine(ContentRoot,"data","logs","module-renderer.log");
            Directory.CreateDirectory(Path.GetDirectoryName(logPath)!);
            File.WriteAllText(logPath,"");
            process.ErrorDataReceived+=(_,e)=> { if(e.Data!=null){logger.LogDebug("Live View: {Line}",e.Data);try{File.AppendAllText(logPath,e.Data+Environment.NewLine);}catch(IOException){}} };
            process.OutputDataReceived+=(_,_)=>{};
            process.BeginErrorReadLine(); process.BeginOutputReadLine();
            using var client=new HttpClient(new SocketsHttpHandler {UseProxy=false}) {Timeout=TimeSpan.FromSeconds(1)};
            client.DefaultRequestHeaders.Add("X-Persona-Module",Token);
            for(var attempt=0;attempt<80;attempt++)
            {
                cancellation.ThrowIfCancellationRequested();
                if(process.HasExited)throw new InvalidOperationException("Renderer exited. Check runtime dependencies.");
                try { using var response=await client.GetAsync($"http://127.0.0.1:{Port}/health",cancellation); if(response.IsSuccessStatusCode)return; }
                catch(HttpRequestException) { }
                catch(TaskCanceledException) when(!cancellation.IsCancellationRequested) { }
                await Task.Delay(250,cancellation);
            }
            throw new TimeoutException("Renderer did not become ready.");
        }
        catch { Kill(); throw; }
        finally { gate.Release(); }
    }
    public async Task PrepareAsync(CancellationToken cancellation)
    {
        await gate.WaitAsync(cancellation);
        try
        {
            var python=ResolvePython();
            if(!File.Exists(python))throw new FileNotFoundException("Voxta's managed Python was not found. Reinstall or repair Voxta, then restart Persona Live View.");
            await ExtractRuntimePayloadAsync(cancellation);
            await PrepareRuntimeAsync(python,cancellation);
        }
        finally { gate.Release(); }
    }
    private string ResolvePython()
    {
        var pythonRoot=Path.Combine(Root,"Data","Python");
        var managed=Directory.Exists(pythonRoot)
            ? Directory.EnumerateDirectories(pythonRoot,"python-*-amd64")
                .OrderByDescending(folder=>folder,StringComparer.OrdinalIgnoreCase)
                .Select(folder=>Path.Combine(folder,"python.exe"))
                .FirstOrDefault(File.Exists)
            : null;
        if(managed is null) return Path.Combine(pythonRoot,"python.exe");
        logger.LogInformation("Using Voxta managed Python at {Python}.",managed);
        return managed;
    }
    private async Task ExtractRuntimePayloadAsync(CancellationToken cancellation)
    {
        var contentRoot=Path.GetFullPath(ContentRoot);
        var prefix="runtime/";
        foreach(var resource in typeof(RendererHost).Assembly.GetManifestResourceNames().Where(name=>name.StartsWith(prefix,StringComparison.Ordinal)))
        {
            var relative=resource[prefix.Length..].Replace('/',Path.DirectorySeparatorChar);
            var destination=Path.GetFullPath(Path.Combine(contentRoot,relative));
            if(!destination.StartsWith(contentRoot+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Module runtime contains an invalid resource path.");
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            await using var source=typeof(RendererHost).Assembly.GetManifestResourceStream(resource)
                ?? throw new InvalidOperationException($"Module resource {resource} is unavailable.");
            await using var target=File.Create(destination);
            await source.CopyToAsync(target,cancellation);
        }
    }
    private async Task PrepareRuntimeAsync(string python,CancellationToken cancellation)
    {
        var info=new ProcessStartInfo(python) { WorkingDirectory=ContentRoot, UseShellExecute=false, CreateNoWindow=true, RedirectStandardError=true, RedirectStandardOutput=true };
        info.Environment.Remove("PYTHONHOME");
        info.Environment.Remove("PYTHONPATH");
        info.Environment["PERSONA_DATA"]=Path.Combine(ContentRoot,"data");
        info.ArgumentList.Add("-m");
        info.ArgumentList.Add("backend.live_bootstrap");
        using var setup=Process.Start(info) ?? throw new InvalidOperationException("Live View runtime setup could not start.");
        var output=setup.StandardOutput.ReadToEndAsync(cancellation);
        var errors=setup.StandardError.ReadToEndAsync(cancellation);
        await setup.WaitForExitAsync(cancellation);
        if(setup.ExitCode!=0)
            throw new InvalidOperationException($"Live View runtime setup failed (exit code {setup.ExitCode}). {await errors}");
        logger.LogInformation("Live View runtime is ready. {Output}",await output);
    }
    private void Kill()
    {
        var owned=Interlocked.Exchange(ref process,null);
        if(owned==null)return;
        try { if(!owned.HasExited)owned.Kill(entireProcessTree:true); }
        catch(InvalidOperationException) { }
        finally { owned.Dispose(); }
    }
    public async ValueTask DisableAsync()
    {
        await gate.WaitAsync();
        try { settings=null; Kill(); } finally {gate.Release();}
    }
    public async ValueTask DisposeAsync() { shutdown.Dispose(); await DisableAsync(); }
}
