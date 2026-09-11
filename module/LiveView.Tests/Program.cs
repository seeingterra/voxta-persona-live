using System.Net;
using System.Net.Sockets;
using System.Net.Http.Json;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging.Abstractions;
using Voxta.Modules.LiveView;

var root=Path.GetFullPath(args.Length>0?args[0]:"Voxta");
var builder=WebApplication.CreateBuilder();
builder.Logging.ClearProviders();
builder.WebHost.UseUrls("http://127.0.0.1:15387");
var app=builder.Build();
await using var renderer=new RendererHost(app.Lifetime,NullLogger<RendererHost>.Instance){Root=root};
new LiveViewStartup(renderer).Configure(a=>a.Run(async c=>{c.Response.ContentType="text/html";await c.Response.WriteAsync("<!doctype html><html><head></head><body>Voxta test shell</body></html>");}))(app);
await app.StartAsync();
using var client=new HttpClient(new SocketsHttpHandler {UseProxy=false}){BaseAddress=new Uri("http://127.0.0.1:15387")};
var checks=0;
void Check(bool ok,string label){if(!ok)throw new Exception(label);checks++;Console.WriteLine("PASS "+label);}
try
{
    var gpuFixture=GpuChoices.Parse("0, NVIDIA GeForce RTX 4080, GPU-card-a, 16376\n1, NVIDIA GeForce RTX 3070, GPU-card-b, 8192\ninvalid row",null);
    Check(gpuFixture.Length==4 && gpuFixture[2].Value=="GPU-card-a" && gpuFixture[3].Label.Contains("8 GB"),"GPU dropdown identifies cards by UUID and shows memory");
    Check(GpuChoices.Parse("",null).Length==2,"GPU dropdown retains Automatic and CPU without NVIDIA detection");
    Check(GpuChoices.Parse("","GPU-unplugged").Last().Value=="GPU-unplugged","GPU dropdown preserves unavailable saved selection");
    using var shell=new HttpRequestMessage(HttpMethod.Get,"/characters/test/chat");
    shell.Headers.Accept.ParseAdd("text/html");shell.Headers.AcceptEncoding.ParseAdd("gzip, br");
    using var response=await client.SendAsync(shell);
    Check((await response.Content.ReadAsStringAsync()).Contains("/persona-live-view/api/voxta/addon/live-view.js"),"SPA bootstrap injected without editing web files");
    var js=await client.GetStringAsync("/persona-live-view/api/voxta/addon/live-view.js");
    Check(js.Contains("location.origin+'/persona-live-view'"),"browser uses same-origin module routes");
    Check((await client.GetStringAsync("/persona-live-view/api/voxta/addon/adapter.json")).Contains("store-"),"adapter resolves installed Voxta assets");
    using var hostile=new HttpRequestMessage(HttpMethod.Post,"/persona-live-view/api/voxta/native-reference");
    hostile.Headers.Add("Origin","https://example.com");
    Check((await client.SendAsync(hostile)).StatusCode==HttpStatusCode.Forbidden,"cross-origin requests rejected");
    Check((await client.GetAsync("/persona-live-view/api/voxta/characters")).StatusCode==HttpStatusCode.NotFound,"standalone API unavailable");
    Check((await client.GetAsync("/persona-live-view/api/session")).StatusCode==HttpStatusCode.ServiceUnavailable,"disabled module does not start renderer");
    var render=args.Contains("--render");
    renderer.Configure(new("Data/LiveView/runtime/Scripts/python.exe",render?"auto":"cpu",5,18766,"http://localhost:5384"));
    Check((await client.GetAsync("/persona-live-view/api/session")).StatusCode==HttpStatusCode.ServiceUnavailable,"renderer requires active chat augmentation");
    var sessionId=Guid.NewGuid();
    Check((await client.GetStringAsync($"/persona-live-view/api/voxta/module-state?sessionId={sessionId}")).Contains("\"active\":false"),"unselected chat reports inactive without loading models");
    await using(var session=new LiveViewSession(renderer,sessionId))
    {
        Check((await client.GetStringAsync($"/persona-live-view/api/voxta/module-state?sessionId={sessionId}")).Contains("\"active\":true"),"selected chat reports activation to its stage");
        Check((await client.GetStringAsync($"/persona-live-view/api/voxta/module-state?sessionId={Guid.NewGuid()}")).Contains("\"active\":false"),"activation is scoped to the correct chat");
        var tokenResponse=await client.GetAsync("/persona-live-view/api/session");
        var body=await tokenResponse.Content.ReadAsStringAsync();
        Check(tokenResponse.IsSuccessStatusCode && body.Contains("token"),"Voxta module starts isolated renderer on demand: "+(tokenResponse.IsSuccessStatusCode?"ready":body));
        using var direct=new HttpClient(new SocketsHttpHandler {UseProxy=false});
        Check((await direct.GetAsync("http://127.0.0.1:18766/health")).StatusCode==HttpStatusCode.Forbidden,"internal renderer requires module authentication");
        direct.DefaultRequestHeaders.Add("X-Persona-Module",renderer.Token);
        Check((await direct.GetStringAsync("http://127.0.0.1:18766/health")).Contains("\"gpu_loaded\":false"),"startup leaves GPU unloaded");
        if(render)
        {
            var chars=JsonDocument.Parse(await direct.GetStringAsync("http://localhost:5384/api/characters/"));
            var character=chars.RootElement.GetProperty("characters").EnumerateArray().First(c=>c.GetProperty("id").GetString()=="b8a6cd74-94a1-50d7-eed7-1953ec81d7ce");
            using var reference=await client.PostAsJsonAsync("/persona-live-view/api/voxta/native-reference",new{path=character.GetProperty("thumbnailUrl").GetString()});
            reference.EnsureSuccessStatusCode();
            var imageId=JsonDocument.Parse(await reference.Content.ReadAsStringAsync()).RootElement.GetProperty("image_id").GetString();
            using var socket=new ClientWebSocket();socket.Options.Proxy=null;
            using var deadline=new CancellationTokenSource(TimeSpan.FromSeconds(100));
            await socket.ConnectAsync(new Uri($"ws://127.0.0.1:15387/persona-live-view/api/voxta/live/{imageId}"),deadline.Token);
            await socket.SendAsync(Encoding.UTF8.GetBytes("{\"mouth\":0.2,\"gaze\":[0.1,0],\"emotion\":\"warm\",\"full_frame\":true}"),WebSocketMessageType.Text,true,deadline.Token);
            var buffer=new byte[65536];var frameCount=0;
            while(frameCount<5)
            {
                using var message=new MemoryStream();WebSocketReceiveResult part;
                do{part=await socket.ReceiveAsync(buffer,deadline.Token);if(part.MessageType==WebSocketMessageType.Close)throw new Exception("Renderer closed before frames");message.Write(buffer,0,part.Count);}while(!part.EndOfMessage);
                if(part.MessageType==WebSocketMessageType.Text){var header=JsonDocument.Parse(message.ToArray());if(header.RootElement.TryGetProperty("error",out var error))throw new Exception(error.GetString());}
                else {Check(message.Length>1000,"real neural image received through native module proxy");frameCount++;}
            }
            socket.Abort();
        }
        await session.OnChatEndAsync(default);
    }
    await Task.Delay(700);
    using var probe=new TcpClient();
    var closed=false;
    try {await probe.ConnectAsync(IPAddress.Loopback,18766);}catch(SocketException){closed=true;}
    Check(closed,"chat end stops renderer and closes its port");
    Check(!renderer.HasSession(sessionId),"ended chat is no longer active");
    await renderer.DisableAsync();
    Check(!renderer.Enabled,"service disable clears module state");
    Console.WriteLine($"{checks} checks passed; {(render ? "five real GPU frames verified and renderer stopped" : "no GPU inference requested")}.");
}
finally {await renderer.DisableAsync();await app.StopAsync();}
