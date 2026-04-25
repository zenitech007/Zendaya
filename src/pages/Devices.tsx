import { PageTransition } from "@/components/PageTransition";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Cpu, HardDrive, Activity, Wifi } from "lucide-react";

const devices = [
  { name: "Processing Unit Alpha", status: "online", type: "CPU", usage: "78%" },
  { name: "Storage Cluster B", status: "online", type: "Storage", usage: "45%" },
  { name: "Network Node 3", status: "warning", type: "Network", usage: "92%" },
  { name: "Analytics Engine", status: "online", type: "Analytics", usage: "63%" },
];

const getIcon = (type: string) => {
  switch (type) {
    case "CPU": return Cpu;
    case "Storage": return HardDrive;
    case "Network": return Wifi;
    default: return Activity;
  }
};

const Devices = () => {
  return (
    <PageTransition>
      <div className="min-h-screen bg-background pb-20 md:pb-6">
        <div className="container mx-auto p-4 md:p-6 max-w-6xl">
          <div className="mb-6">
            <h1 className="text-2xl md:text-3xl font-bold mb-2">Connected Devices</h1>
            <p className="text-muted-foreground">Manage your system components</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {devices.map((device) => {
              const Icon = getIcon(device.type);
              return (
                <Card key={device.name} className="hover:shadow-lg transition-shadow">
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-base font-medium">{device.name}</CardTitle>
                    <Badge variant={device.status === "online" ? "default" : "destructive"}>
                      {device.status}
                    </Badge>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Icon className="w-5 h-5 text-primary" />
                        <span className="text-sm text-muted-foreground">{device.type}</span>
                      </div>
                      <span className="text-lg font-semibold">{device.usage}</span>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </div>
    </PageTransition>
  );
};

export default Devices;
