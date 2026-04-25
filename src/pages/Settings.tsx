import { PageTransition } from "@/components/PageTransition";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

const Settings = () => {
  return (
    <PageTransition>
      <div className="min-h-screen bg-background pb-20 md:pb-6">
        <div className="container mx-auto p-4 md:p-6 max-w-4xl">
          <div className="mb-6">
            <h1 className="text-2xl md:text-3xl font-bold mb-2">Settings</h1>
            <p className="text-muted-foreground">Configure your system preferences</p>
          </div>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Notifications</CardTitle>
                <CardDescription>Manage system alerts and notifications</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="connection">Connection Status</Label>
                  <Switch id="connection" defaultChecked />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="errors">Error Alerts</Label>
                  <Switch id="errors" defaultChecked />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="updates">System Updates</Label>
                  <Switch id="updates" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance</CardTitle>
                <CardDescription>Optimize system performance</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="auto-optimize">Auto Optimization</Label>
                  <Switch id="auto-optimize" defaultChecked />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="power-save">Power Saving Mode</Label>
                  <Switch id="power-save" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Voice Control</CardTitle>
                <CardDescription>Configure voice assistant settings</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="wake-word">Wake Word Detection</Label>
                  <Switch id="wake-word" defaultChecked />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <Label htmlFor="voice-feedback">Voice Feedback</Label>
                  <Switch id="voice-feedback" defaultChecked />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageTransition>
  );
};

export default Settings;
