import { PageTransition } from "@/components/PageTransition";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mic, MicOff, Volume2 } from "lucide-react";
import { useState } from "react";

const Voice = () => {
  const [isListening, setIsListening] = useState(false);

  return (
    <PageTransition>
      <div className="min-h-screen bg-background pb-20 md:pb-6">
        <div className="container mx-auto p-4 md:p-6 max-w-4xl">
          <div className="mb-6">
            <h1 className="text-2xl md:text-3xl font-bold mb-2">Voice Control</h1>
            <p className="text-muted-foreground">Control your system with voice commands</p>
          </div>

          <div className="space-y-4">
            <Card className="text-center">
              <CardHeader>
                <CardTitle>Voice Assistant</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex justify-center">
                  <Button
                    size="lg"
                    onClick={() => setIsListening(!isListening)}
                    className={`rounded-full h-24 w-24 ${
                      isListening ? "bg-destructive hover:bg-destructive/90" : ""
                    }`}
                  >
                    {isListening ? (
                      <MicOff className="w-10 h-10" />
                    ) : (
                      <Mic className="w-10 h-10" />
                    )}
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">
                  {isListening ? "Listening..." : "Tap to activate voice control"}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Volume2 className="w-5 h-5" />
                  Available Commands
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li>• "Show system status"</li>
                  <li>• "Enable all devices"</li>
                  <li>• "Run diagnostics"</li>
                  <li>• "Optimize performance"</li>
                  <li>• "Display metrics"</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageTransition>
  );
};

export default Voice;
