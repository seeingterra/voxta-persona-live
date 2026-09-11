using System.Net;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;

namespace Voxta.Modules.LiveView;

public sealed class LiveViewStartup(RendererHost renderer) : IStartupFilter
{
    private const string Prefix="/persona-live-view";
    private const string Tag="<script type=\"module\" src=\"/persona-live-view/api/voxta/addon/live-view.js\"></script>";
    public Action<IApplicationBuilder> Configure(Action<IApplicationBuilder> next) => app =>
    {
        app.UseWebSockets();
        app.Use(async (context, following) =>
        {
            if(context.Request.Path.StartsWithSegments(Prefix,out var rest))
            {
                await Handle(context,rest.Value ?? "/"); return;
            }
            if(!Local(context) || context.Request.Method!="GET" || !context.Request.Headers.Accept.ToString().Contains("text/html"))
            { await following(); return; }
            // Only the SPA shell is transformed. Voxta's files remain untouched.
            var original=context.Response.Body;
            var encoding=context.Request.Headers.AcceptEncoding;
            var etag=context.Request.Headers.IfNoneMatch;
            var modified=context.Request.Headers.IfModifiedSince;
            context.Request.Headers.Remove("Accept-Encoding");
            context.Request.Headers.Remove("If-None-Match");
            context.Request.Headers.Remove("If-Modified-Since");
            await using var buffer=new MemoryStream();
            context.Response.Body=buffer;
            try
            {
                await following();
                buffer.Position=0;
                if(context.Response.StatusCode==200 && context.Response.ContentType?.StartsWith("text/html")==true && !context.Response.Headers.ContainsKey("Content-Encoding"))
                {
                    var html=await new StreamReader(buffer,Encoding.UTF8).ReadToEndAsync(context.RequestAborted);
                    html=html.Replace("</head>",Tag+"</head>",StringComparison.OrdinalIgnoreCase);
                    var bytes=Encoding.UTF8.GetBytes(html);
                    context.Response.ContentLength=bytes.Length;
                    context.Response.Headers.Remove("ETag");
                    context.Response.Headers.CacheControl="no-store";
                    await original.WriteAsync(bytes,context.RequestAborted);
                }
                else await buffer.CopyToAsync(original,context.RequestAborted);
            }
            finally { context.Response.Body=original; context.Request.Headers.AcceptEncoding=encoding; context.Request.Headers.IfNoneMatch=etag; context.Request.Headers.IfModifiedSince=modified; }
        });
        next(app);
    };

    private bool Local(HttpContext c)
    {
        var address=c.Connection.RemoteIpAddress;
        return address!=null && IPAddress.IsLoopback(address) && Uri.TryCreate($"http://{c.Request.Host}",UriKind.Absolute,out var host) && host.IsLoopback;
    }
    private async Task Handle(HttpContext c,string path)
    {
        c.Response.Headers.CacheControl="no-store";
        c.Response.Headers.XContentTypeOptions="nosniff";
        if(!Local(c) || (c.Request.Headers.Origin.Count>0 && c.Request.Headers.Origin.ToString()!=$"{c.Request.Scheme}://{c.Request.Host}") || c.Request.Headers["Sec-Fetch-Site"]=="cross-site")
        {c.Response.StatusCode=403;return;}
        try
        {
            if(path=="/api/voxta/module-state" && c.Request.Method=="GET")
            {
                var active=Guid.TryParse(c.Request.Query["sessionId"],out var sessionId) && renderer.HasSession(sessionId);
                await c.Response.WriteAsJsonAsync(new{enabled=renderer.Enabled,active});return;
            }
            if(path.StartsWith("/api/voxta/addon/") && c.Request.Method=="GET")
            {
                var name=path["/api/voxta/addon/".Length..];
                if(name=="adapter.json")
                {
                    var assets=Path.Combine(renderer.Root,"wwwroot","assets");
                    var chatFile=Directory.GetFiles(assets,"ChatPage-*.js").OrderByDescending(Path.GetFileName,StringComparer.Ordinal).FirstOrDefault()
                        ?? throw new InvalidOperationException("Voxta chat assets were not found.");
                    var chat=File.ReadAllText(chatFile);
                    string Match(string pattern) {var match=Regex.Match(chat,pattern);return match.Success ? "/assets/"+match.Groups[1].Value : throw new InvalidOperationException("This Voxta version requires an updated Live View UI adapter.");}
                    var notifications=Directory.GetFiles(assets,"ui-store-*.js").OrderByDescending(Path.GetFileName,StringComparer.Ordinal).FirstOrDefault();
                    await c.Response.WriteAsJsonAsync(new {store=Match(@"\./(store-[^""\s]+\.js)"),audio=Match(@"\./(AudioPlaybackService-[^""\s]+\.js)"),notifications=notifications is null ? null : "/assets/"+Path.GetFileName(notifications)}); return;
                }
                if(name is not ("live-view.js" or "live-view.css")){c.Response.StatusCode=404;return;}
                c.Response.ContentType=name.EndsWith(".js")?"text/javascript":"text/css";
                await using var stream=typeof(VoxtaModule).Assembly.GetManifestResourceStream(name)!;
                await stream.CopyToAsync(c.Response.Body,c.RequestAborted);return;
            }
            var live=Regex.IsMatch(path,@"^/api/voxta/live/[a-f0-9]{32}$");
            var allowed=path is "/api/session" or "/api/voxta/status" or "/api/voxta/native-reference" or "/api/voxta/install" or "/api/voxta/install-status" || Regex.IsMatch(path,@"^/api/voxta/matte/[a-f0-9]{32}$");
            if(!live && !allowed){c.Response.StatusCode=404;return;}
            if(c.Request.ContentLength>36*1024*1024){c.Response.StatusCode=413;return;}
            if(c.Request.Method is not ("GET" or "POST")){c.Response.StatusCode=405;return;}
            if(path=="/api/voxta/install")
            {
                if(c.Request.Method!="POST"){c.Response.StatusCode=405;return;}
                await renderer.PrepareAsync(c.RequestAborted);
                await c.Response.WriteAsJsonAsync(new {ready=true});return;
            }
            if(path=="/api/voxta/install-status")
            {
                if(c.Request.Method!="GET"){c.Response.StatusCode=405;return;}
                await c.Response.WriteAsJsonAsync(new {ready=renderer.IsPrepared});return;
            }
            if(path=="/api/session" && !renderer.IsPrepared)
            {
                c.Response.StatusCode=503;
                await c.Response.WriteAsJsonAsync(new {detail="Live View setup is required. Use Start animation to run the one-time installer."});
                return;
            }
            await renderer.EnsureStartedAsync(c.RequestAborted);
            if(live)
            {
                if(!c.WebSockets.IsWebSocketRequest){c.Response.StatusCode=400;return;}
                using var upstream=new ClientWebSocket();
                upstream.Options.Proxy=null;
                upstream.Options.SetRequestHeader("Origin",renderer.Origin);
                await upstream.ConnectAsync(new Uri($"ws://127.0.0.1:{renderer.Port}{path}?token={renderer.Token}"),c.RequestAborted);
                using var downstream=await c.WebSockets.AcceptWebSocketAsync();
                using var cancel=CancellationTokenSource.CreateLinkedTokenSource(c.RequestAborted);
                var a=Relay(upstream,downstream,cancel.Token);var b=Relay(downstream,upstream,cancel.Token);
                await Task.WhenAny(a,b);await cancel.CancelAsync();
                try {await Task.WhenAll(a,b);}catch(OperationCanceledException){}catch(WebSocketException){}
                return;
            }
            using var client=new HttpClient(new SocketsHttpHandler {UseProxy=false}) {Timeout=TimeSpan.FromSeconds(120)};
            using var request=new HttpRequestMessage(new HttpMethod(c.Request.Method),$"http://127.0.0.1:{renderer.Port}{path}");
            request.Headers.Add("X-Persona-Module",renderer.Token);
            request.Headers.Add("X-Persona-Token",renderer.Token);
            if(c.Request.Method=="POST")
            {
                request.Content=new StreamContent(c.Request.Body);
                request.Content.Headers.TryAddWithoutValidation("Content-Type",c.Request.ContentType);
            }
            using var response=await client.SendAsync(request,HttpCompletionOption.ResponseHeadersRead,c.RequestAborted);
            c.Response.StatusCode=(int)response.StatusCode;
            c.Response.ContentType=response.Content.Headers.ContentType?.ToString();
            await response.Content.CopyToAsync(c.Response.Body,c.RequestAborted);
        }
        catch(Exception e) when(e is not OperationCanceledException)
        {
            if(!c.Response.HasStarted){c.Response.StatusCode=503;await c.Response.WriteAsJsonAsync(new{detail=e.Message});}
        }
    }
    private static async Task Relay(WebSocket source,WebSocket destination,CancellationToken token)
    {
        var bytes=new byte[64*1024];
        while(!token.IsCancellationRequested)
        {
            var result=await source.ReceiveAsync(bytes.AsMemory(),token);
            if(result.MessageType==WebSocketMessageType.Close)return;
            await destination.SendAsync(bytes.AsMemory(0,result.Count),result.MessageType,result.EndOfMessage,token);
        }
    }
}
