'use client';

import { useActionState } from 'react';
import { useFormStatus } from 'react-dom';
import { signUpWithEmail } from '@/lib/actions/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal } from 'lucide-react';

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" className="w-full" disabled={pending}>
      {pending ? 'Registering...' : 'Sign Up'}
    </Button>
  );
}

export function SignUpForm() {
  const [state, formAction] = useActionState(signUpWithEmail, null);

  return (
    <Card className="glassmorphism">
      <CardContent className="pt-6">
        {state?.message?.startsWith('Success!') ? (
          <Alert>
            <Terminal className="h-4 w-4" />
            <AlertTitle>Registration Pending</AlertTitle>
            <AlertDescription>
                {state.message}
            </AlertDescription>
          </Alert>
        ) : (
          <form action={formAction} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input id="email" name="email" type="email" placeholder="operative@zendaya.net" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" type="password" placeholder="Must be at least 8 characters" required />
            </div>
            {state?.message && <p className="text-sm text-destructive">{state.message}</p>}
            <SubmitButton />
          </form>
        )}
      </CardContent>
    </Card>
  );
}
