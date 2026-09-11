using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Voxta.Abstractions.Modules;
using Voxta.Abstractions.Registration;
using Voxta.Model.Shared;

namespace Voxta.Modules.LiveView;

public class VoxtaModule : IVoxtaModule
{
    public void Configure(IVoxtaModuleBuilder builder)
    {
        builder.Register(new()
        {
            ServiceName = "PersonaLiveView", Label = "Persona Live View", Single = true,
            Experimental = true, Pricing = ServiceDefinitionPricing.Free,
            SupportsExplicitContent = true,
            Hosting = ServiceDefinitionHosting.Builtin,
            Supports = new() { ChatAugmentations = new(ServiceDefinitionCategoryScore.High) },
            Augmentations = [new("persona_live_view", "Live view", "Local animated character inside the chat stage.")],
            ModuleConfigurationProviderType = typeof(LiveViewConfiguration),
            ModuleConfigurationFieldsRequiringReload = ["Device", "FrameRate", "RendererPort", "VoxtaUrl"]
        });
        builder.AddChatAugmentationsService<LiveViewService>("PersonaLiveView");
        builder.Services.AddSingleton<RendererHost>();
        builder.Services.AddTransient<IStartupFilter, LiveViewStartup>();
    }
}
