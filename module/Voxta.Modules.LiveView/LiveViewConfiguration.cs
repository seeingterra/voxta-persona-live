using Voxta.Abstractions.Registration;
using Voxta.Abstractions.Security;
using Voxta.Model.Shared.Forms;

namespace Voxta.Modules.LiveView;

public record LiveViewSettings(string Device, int Fps, int Port, string VoxtaUrl);

public class LiveViewConfiguration : ModuleConfigurationProviderBase, IModuleConfigurationProvider
{
    public static readonly FormChoicesField Device = new() { Name="Device", Label="Graphics processor", DefaultValue="auto", Choices=GpuChoices.Defaults, Text="Automatic prefers the smaller suitable GPU, leaving the larger card for Voxta. Select a card to always use it." };
    public static readonly FormIntField Fps = new() { Name="FrameRate", Label="Maximum frames per second", DefaultValue=15, Min=1, Max=30, Text="1–30 frames per second." };
    public static readonly FormIntField Port = new() { Name="RendererPort", Label="Internal renderer port", DefaultValue=8766, Min=1024, Max=65535, Text="1024–65535. Loopback only; managed by this module." };
    public static readonly FormTextField Url = new() { Name="VoxtaUrl", Label="Local Voxta address", DefaultValue="http://localhost:5384", Text="Use this same address when opening Voxta in your browser." };
    public async Task<FormField[]> GetModuleConfigurationFieldsAsync(IAuthenticationContext auth, ISettingsSource settings, CancellationToken cancellationToken)
    {
        var choices=await GpuChoices.DetectAsync(settings.GetOptional(Device),cancellationToken);
        var device=new FormChoicesField { Name=Device.Name, Label=Device.Label, DefaultValue="auto", Choices=choices, Text=Device.Text };
        return [device, Fps, Port, Url];
    }
    public static LiveViewSettings Read(ISettingsSource source) => new(source.GetRequired(Device), source.GetRequired(Fps), source.GetRequired(Port), source.GetRequired(Url));
}
