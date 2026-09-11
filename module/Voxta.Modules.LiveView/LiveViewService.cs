using Microsoft.Extensions.Logging;
using Voxta.Abstractions.Chats.Objects.Chats;
using Voxta.Abstractions.Chats.Sessions;
using Voxta.Abstractions.Security;
using Voxta.Abstractions.Services;
using Voxta.Abstractions.Services.ChatAugmentations;
using Voxta.Model.Shared;

namespace Voxta.Modules.LiveView;

public class LiveViewService(RendererHost renderer, ILogger<LiveViewService> logger) : ServiceBase(logger), IChatAugmentationsService
{
    protected override async Task InitializeAsync(CancellationToken cancellationToken)
    {
        await base.InitializeAsync(cancellationToken);
        renderer.Configure(LiveViewConfiguration.Read(ModuleConfiguration));
    }
    public Task<AugmentationPlanItem[]> PlanAsync(IChatAugmentationPlanContext context, CancellationToken cancellationToken)
    {
        var settings=LiveViewConfiguration.Read(ModuleConfiguration);
        return Task.FromResult<AugmentationPlanItem[]>([new()
        {
            Key="persona_live_view", Label="Live view", Description="Local animated character inside the chat stage.",
            Activation=AugmentationActivation.Automatic,
            ActivateAsync=(session,_)=>
            {
                renderer.Configure(settings);
                var ids=session is IChatSessionData data ? new[]{session.SessionId,data.ChatId} : new[]{session.SessionId};
                var instance=new LiveViewSession(renderer,ids);
                return Task.FromResult<IChatAugmentationServiceInstanceBase?>(instance);
            }
        }]);
    }
    // Voxta disposes the factory after activation. The returned per-chat instance
    // exclusively owns its lifetime; factory disposal must not stop that instance.
}

public sealed class LiveViewSession : IChatAugmentationServiceInstanceBase, IChatEndAugmentation
{
    private RendererHost? renderer;
    private readonly Guid[] ids;
    public LiveViewSession(RendererHost host, params Guid[] sessionIds) { renderer=host; ids=sessionIds.Length>0?sessionIds.Distinct().ToArray():[Guid.NewGuid()];foreach(var id in ids)host.AddSession(id); }
    public ServiceTypes[] GetRequiredServiceTypes() => [];
    public string[] GetAugmentationNames() => ["persona_live_view"];
    public ValueTask OnChatEndAsync(CancellationToken cancellationToken) => DisposeAsync();
    public async ValueTask DisposeAsync()
    {
        var host=Interlocked.Exchange(ref renderer,null);
        if(host!=null)foreach(var id in ids)await host.RemoveSessionAsync(id);
    }
}
