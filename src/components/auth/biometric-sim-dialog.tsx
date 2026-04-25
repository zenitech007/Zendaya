'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScanFace, Mic, ShieldCheck, ShieldAlert } from 'lucide-react';

type BiometricType = 'face' | 'voice';

const statusMessages = {
  scanning: {
    face: 'Scanning facial signature...',
    voice: 'Analyzing voiceprint...',
  },
  success: {
    face: 'Face ID Authorized',
    voice: 'Voiceprint Confirmed',
  },
  failure: {
    face: 'Facial Signature Not Recognized',
    voice: 'Voiceprint Mismatch',
  },
};

export default function BiometricSimDialog({ type }: { type: BiometricType }) {
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState<'idle' | 'scanning' | 'success' | 'failure'>('idle');

  useEffect(() => {
    if (!isOpen) {
      setStatus('idle');
      return;
    }

    setStatus('scanning');
    const scanTimer = setTimeout(() => {
      // Simulate a random success or failure
      const result = Math.random() > 0.3 ? 'success' : 'failure';
      setStatus(result);
    }, 2500);

    const closeTimer = setTimeout(() => {
        setIsOpen(false);
    }, 4500);

    return () => {
      clearTimeout(scanTimer);
      clearTimeout(closeTimer);
    };
  }, [isOpen]);

  const Icon = type === 'face' ? ScanFace : Mic;
  const label = type === 'face' ? 'Face ID' : 'Voice Login';

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          <Icon className="mr-2 h-4 w-4" />
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md glassmorphism">
        <DialogHeader>
          <DialogTitle className="text-center text-xl text-glow">{label} Authentication</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col items-center justify-center space-y-6 p-8 min-h-[200px]">
          {status === 'scanning' && (
            <>
              {type === 'face' ? (
                <ScanFace className="h-20 w-20 text-primary animate-pulse" />
              ) : (
                <Mic className="h-20 w-20 text-primary animate-pulse" />
              )}
              <p className="text-muted-foreground animate-pulse">{statusMessages.scanning[type]}</p>
            </>
          )}
          {status === 'success' && (
            <>
              <ShieldCheck className="h-20 w-20 text-online-green" />
              <p className="font-semibold text-lg text-online-green">{statusMessages.success[type]}</p>
            </>
          )}
          {status === 'failure' && (
            <>
              <ShieldAlert className="h-20 w-20 text-destructive" />
              <p className="font-semibold text-lg text-destructive">{statusMessages.failure[type]}</p>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
