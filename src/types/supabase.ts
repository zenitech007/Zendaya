/**
 * This file is an auto-generated placeholder.
 * For a real project, generate this file using:
 * npx supabase gen types typescript --project-id <your-project-id> > src/types/supabase.ts
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      zendaya_messages: {
        Row: {
          id: string;
          created_at: string;
          session_id: string;
          user_id: string | null;
          role: "user" | "ai" | "system";
          text: string;
          meta: Json | null;
        };
        Insert: {
          id?: string;
          created_at?: string;
          session_id: string;
          user_id?: string | null;
          role: "user" | "ai" | "system";
          text: string;
          meta?: Json | null;
        };
        Update: {
          id?: string;
          created_at?: string;
          session_id?: string;
          user_id?: string | null;
          role?: "user" | "ai" | "system";
          text?: string;
          meta?: Json | null;
        };
      };
      zendaya_sessions: {
        Row: {
          id: string;
          created_at: string;
          user_id: string;
        };
        Insert: {
          id?: string;
          created_at?: string;
          user_id: string;
        };
        Update: {
          id?: string;
          created_at?: string;
          user_id?: string;
        };
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      [_ in never]: never;
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
}