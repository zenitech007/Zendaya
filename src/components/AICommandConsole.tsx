"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export const AICommandConsole = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [command, setCommand] = useState("");

  const handleSend = () => {
    if (command.trim()) {
      console.log("AI Command:", command);
      setCommand("");
    }
  };

  return (
    <>
      {/* Trigger Button */}
      <Button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-20 right-4 md:bottom-6 z-40 rounded-full h-14 w-14 shadow-lg bg-primary/90 backdrop-blur hover:bg-primary"
      >
        <Sparkles className="w-6 h-6" />
      </Button>

      {/* Console Panel */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            />

            {/* Panel */}
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="fixed bottom-0 left-0 right-0 z-50 max-h-[80vh]"
            >
              <div className="bg-background/95 backdrop-blur-xl border-t border-border rounded-t-3xl shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-border/50">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-primary" />
                    <h3 className="font-semibold text-lg">AI Command Console</h3>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsOpen(false)}
                  >
                    <ChevronDown className="w-5 h-5" />
                  </Button>
                </div>

                {/* Content */}
                <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
                  <div className="space-y-2">
                    <div className="text-sm text-muted-foreground">
                      Quick Commands
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {["System Status", "Enable All", "Optimize", "Diagnostics"].map((cmd) => (
                        <Button
                          key={cmd}
                          variant="outline"
                          size="sm"
                          onClick={() => setCommand(cmd)}
                          className="text-xs"
                        >
                          {cmd}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Input */}
                  <div className="flex gap-2">
                    <Input
                      value={command}
                      onChange={(e) => setCommand(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleSend()}
                      placeholder="Type your command..."
                      className="flex-1 bg-muted/50"
                    />
                    <Button onClick={handleSend} size="icon">
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
};
