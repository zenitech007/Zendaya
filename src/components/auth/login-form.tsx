'use client';

import { useActionState } from 'react';
import { useFormStatus } from 'react-dom';
import { signInWithEmail, signInWithMagicLink, signInWithOAuth } from '@/lib/actions/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { AlertTriangle, TestTube, ChevronsRight } from 'lucide-react';
import BiometricSimDialog from './biometric-sim-dialog';
import { Link } from 'react-router-dom';

function GoogleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M21.35 12.08c0-.75-.07-1.48-.2-2.18h-8.85v4.1h5.1c-.22 1.34-.88 2.5-1.9 3.24v2.7h3.48c2.04-1.88 3.22-4.76 3.22-8.1Z"/><path fill="currentColor" d="M12.3 22c2.75 0 5.06-1 6.7-2.69l-3.48-2.7c-.83.6-1.93.9-3.22.9-2.58 0-4.78-1.7-5.5-4.04H3.34v2.78c1.6 3.2 4.9 5.45 8.96 5.45Z"/><path fill="currentColor" d="M6.8 14.3c-.15-.46-.23-.96-.23-1.48s.08-1.02.23-1.48V8.55H3.34A9.9 9.9 0 0 0 2.3 12.8c0 1.48.33 2.88.94 4.15Z"/><path fill="currentColor" d="M12.3 6.33c1.56 0 2.85.55 3.82 1.48l3.04-3.04C17.35 2.8 15.05 1.8 12.3 1.8c-4.05 0-7.36 2.25-8.96 5.45l3.48 2.78C7.52 8.02 9.72 6.33 12.3 6.33Z"/></svg>
  );
}

function SubmitButton({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" className="w-full" disabled={pending}>
      {pending ? 'Authorizing...' : children}
    </Button>
  );
}

function OAuthButtons() {
    return (
        <div className="grid grid-cols-1 gap-4">
          <form action={signInWithOAuth}>
            <input type="hidden" name="provider" value="google" />
            <Button variant="outline" className="w-full" type="submit">
              <GoogleIcon />
              Google
            </Button>
          </form>
        </div>
    )
}

function MagicLinkForm() {
    const [state, formAction] = useActionState(signInWithMagicLink, null);

    return (
        <form action={formAction} className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="magic-email">Email Address</Label>
                <Input id="magic-email" name="email" type="email" placeholder="operative@zendaya.net" required />
            </div>
            {state?.message && !state.message.includes('Success') && (
              <p className="text-sm text-destructive">{state.message}</p>
            )}
            {state?.message && state.message.includes('Success') && (
              <p className="text-sm text-amber-pulse">{state.message}</p>
            )}
            <SubmitButton>Send Magic Link</SubmitButton>
        </form>
    );
}

export function LoginForm() {
  const [state, formAction] = useActionState(signInWithEmail, null);
  const isSupabaseNotConfigured = state?.message.includes('Supabase');

  const handleTestLogin = () => {
    const emailInput = document.getElementById('email') as HTMLInputElement;
    const passwordInput = document.getElementById('password') as HTMLInputElement;
    if (emailInput && passwordInput) {
      emailInput.value = 'test@example.com';
      passwordInput.value = 'password';
    }
  }

  return (
    <Card className="glassmorphism">
      <CardHeader>
        <OAuthButtons />
        <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">Or continue with</span>
            </div>
        </div>
      </CardHeader>
      <CardContent>
        {isSupabaseNotConfigured ? (
          <div className="flex flex-col items-center text-center gap-4 bg-amber-pulse/10 p-4 rounded-lg border border-amber-pulse/20">
            <AlertTriangle className="text-amber-pulse" />
            <h3 className="font-semibold text-amber-pulse">Supabase Not Configured</h3>
            <p className="text-sm text-muted-foreground">
              Your Supabase project credentials are not set up. Please add your <code className="bg-background/50 px-1 py-0.5 rounded">NEXT_PUBLIC_SUPABASE_URL</code> and <code className="bg-background/50 px-1 py-0.5 rounded">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to a <code className="bg-background/50 px-1 py-0.5 rounded">.env.local</code> file in the root of your project.
            </p>
          </div>
        ) : (
          <form action={formAction} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input id="email" name="email" type="email" placeholder="operative@zendaya.net" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" type="password" required />
            </div>
            {state?.message && <p className="text-sm text-destructive">{state.message}</p>}
            <SubmitButton>Sign In</SubmitButton>
          </form>
        )}
      </CardContent>
      {!isSupabaseNotConfigured && (
        <CardFooter className="flex-col gap-4">
            <div className="w-full flex flex-col gap-4">
                <Button variant="outline" className="w-full" onClick={handleTestLogin}>
                    <TestTube className="mr-2 h-4 w-4" />
                    Test Login
                </Button>
                <Link to="/dashboard" className="w-full">
                    <Button variant="secondary" className="w-full">
                        Bypass Login
                        <ChevronsRight className="ml-2 h-4 w-4" />
                    </Button>
                </Link>
            </div>
          <Separator className="my-4"/>
          <div className="w-full">
              <p className="text-center text-sm text-muted-foreground mb-4">Alternative Logins</p>
              <MagicLinkForm />
              <div className="grid grid-cols-2 gap-4 mt-4">
                  <BiometricSimDialog type="face" />
                  <BiometricSimDialog type="voice" />
              </div>
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
