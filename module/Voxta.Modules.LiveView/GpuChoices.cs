using System.Diagnostics;
using System.Globalization;
using Voxta.Model.Shared.Forms;

namespace Voxta.Modules.LiveView;

public static class GpuChoices
{
    public static FormChoice[] Defaults => [new("Automatic — choose a suitable GPU", "auto"),new("CPU — no GPU memory", "cpu")];

    public static FormChoice[] Parse(string output,string? selected)
    {
        var choices=new List<FormChoice>(Defaults);
        var found=new HashSet<string>(StringComparer.Ordinal){"auto","cpu"};
        foreach(var line in output.Split('\n',StringSplitOptions.RemoveEmptyEntries))
        {
            var fields=line.Trim().Split(',');
            if(fields.Length!=4 || !int.TryParse(fields[0].Trim(),out var index))continue;
            var name=fields[1].Trim();var id=fields[2].Trim();
            if(!id.StartsWith("GPU-",StringComparison.Ordinal) || !found.Add(id))continue;
            var memory=double.TryParse(fields[3].Trim(),NumberStyles.Float,CultureInfo.InvariantCulture,out var mb)
                ? $" · {(mb/1024).ToString("0.#",CultureInfo.InvariantCulture)} GB" : "";
            choices.Add(new($"GPU {index}: {name}{memory}",id));
        }
        // Keep an unplugged or temporarily unavailable selection instead of silently changing cards.
        if(!string.IsNullOrWhiteSpace(selected) && selected.StartsWith("GPU-",StringComparison.Ordinal) && !found.Contains(selected))
            choices.Add(new($"Previously selected GPU — currently unavailable ({selected})",selected));
        return choices.ToArray();
    }

    public static async Task<FormChoice[]> DetectAsync(string? selected,CancellationToken cancellation)
    {
        using var timeout=CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        timeout.CancelAfter(TimeSpan.FromSeconds(4));
        using var process=new Process {StartInfo=new ProcessStartInfo(NvidiaSmiPath()) {UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true}};
        process.StartInfo.ArgumentList.Add("--query-gpu=index,name,uuid,memory.total");
        process.StartInfo.ArgumentList.Add("--format=csv,noheader,nounits");
        try
        {
            process.Start();
            var stdout=process.StandardOutput.ReadToEndAsync(timeout.Token);
            var stderr=process.StandardError.ReadToEndAsync(timeout.Token);
            await process.WaitForExitAsync(timeout.Token);
            var output=await stdout;await stderr;
            return Parse(process.ExitCode==0?output:"",selected);
        }
        catch(OperationCanceledException) when(!cancellation.IsCancellationRequested) {return Parse("",selected);}
        catch(System.ComponentModel.Win32Exception) {return Parse("",selected);}
        finally
        {
            try {if(!process.HasExited)process.Kill(entireProcessTree:true);}catch(InvalidOperationException){}
        }
    }
    private static string NvidiaSmiPath()
    {
        var system=Path.Combine(Environment.SystemDirectory,"nvidia-smi.exe");
        return File.Exists(system) ? system : "nvidia-smi";
    }
}
