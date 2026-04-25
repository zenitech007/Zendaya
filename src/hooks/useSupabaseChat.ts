import { useEffect, useState } from "react";
import { User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabaseClient";
import { getOrCreateSession } from "../lib/sessionManager";
import { useChatStore } from "./useChatStore";
import { Message } from "../types";

/**
 * Hook to manage Supabase session, auth, and real-time message sync.
 * This hook initializes the chat session and syncs with the Zustand store.
 */
export const useSupabaseChat = () => {
  // Get setters from the store
  const {
    setSessionId,
    setMessages,
    setIsLoading,
    addMessage,
    updateMessage,
    removeMessage,
    addSystemMessage,
  } = useChatStore();

  const [user, setUser] = useState<User | null>(null);

  // 1. Handle Auth
  // ✅ FIX: Simplified auth logic to prevent race conditions and loops.
  useEffect(() => {
    // ... (This auth logic is correct and unchanged)
    if (!supabase) {
      addSystemMessage("Supabase client not configured.", true);
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    const setupAuthAndListen = async () => {
      // 1. Get initial session
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (isMounted) {
          const currentUser = session?.user ?? null;
          setUser(currentUser);

          // 2. If no session, sign in anonymously
          if (!session) {
            const { data: anonData, error } =
              await supabase.auth.signInAnonymously();
            if (error) throw error;
            if (isMounted) setUser(anonData?.user ?? null);
          }
        }
      } catch (error: any) {
        console.error("Auth error:", error);
        if (isMounted) {
          addSystemMessage(`Auth error: ${error.message}`, true);
          setIsLoading(false);
        }
      }
    };

    setupAuthAndListen();

    // 3. Listen for future auth changes (e.g., login, logout)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (isMounted) {
        setUser(session?.user ?? null);
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [addSystemMessage, setIsLoading]); // This effect runs only once

  // 2. Handle Session, Data Fetching, and Real-time Subscription
  // This effect now correctly depends on `user` and will run once auth is stable.
  useEffect(() => {
    if (!supabase) {
      setIsLoading(false);
      return;
    }

    // Wait until the user object is available.
    if (!user) {
      setIsLoading(true); // Show loader while waiting for user
      return;
    }

    let isMounted = true;
    let channel: any = null; // Supabase realtime channel

    const initializeSessionAndFetch = async () => {
      // ✅ FIX: Use `useChatStore.getState()` to read the current state
      // without subscribing to it inside an effect.
      if (useChatStore.getState().isLoading) {
        setIsLoading(true);
      }

      try {
        const sessionData = await getOrCreateSession(user.id);
        const currentSessionId = sessionData?.id || null;

        if (!currentSessionId) {
          throw new Error("Critical Error: Could not create or get a session ID.");
        }
        if (!isMounted) return;

        setSessionId(currentSessionId);
        console.log("ZendayaChat: Using session ID:", currentSessionId);

        // 1. Fetch initial messages
        const { data, error } = await supabase
          .from("zendaya_messages")
          .select("*")
          .eq("session_id", currentSessionId)
          .order("created_at", { ascending: true });

        if (!isMounted) return;
        if (error) throw error;

        if (data) {
          if (data.length === 0) {
            addSystemMessage(
              "Zendaya initialized. Ask or speak naturally to interact with your AI system."
            );
          } else {
            setMessages(data as Message[]);
          }
        }

        // 2. Subscribe to real-time changes
        channel = supabase
          .channel(`zendaya_messages_${currentSessionId}`)
          .on<Message>(
            "postgres_changes",
            {
              event: "*",
              schema: "public",
              table: "zendaya_messages",
              filter: `session_id=eq.${currentSessionId}`,
            },
            (payload) => {
              if (!isMounted) return;

              if (payload.eventType === "INSERT") {
                const newMessage = payload.new as Message;
                const optimisticId = newMessage.meta?.optimisticId;

                if (optimisticId) {
                  updateMessage(
                    optimisticId,
                    newMessage.text,
                    newMessage.meta,
                    newMessage.id
                  );
                } else {
                  addMessage(newMessage);
                }
              }

              if (payload.eventType === "UPDATE") {
                updateMessage(
                  payload.new.id,
                  payload.new.text,
                  payload.new.meta,
                  payload.new.id
                );
              }

              if (payload.eventType === "DELETE") {
                const oldId = (payload.old as any)?.id;
                if (oldId) removeMessage(oldId);
              }
            }
          )
          .subscribe((status, err) => {
            if (status === "SUBSCRIBED") {
              console.log("Realtime channel subscribed successfully!");
            } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
              console.error("Realtime subscription error:", err || status);
              if (isMounted) {
                addSystemMessage(
                  `Realtime connection error: ${err?.message || status}`,
                  true
                );
              }
            }
          });
      } catch (err: any) {
        console.error("Error in initializeSessionAndFetch:", err);
        if (isMounted) addSystemMessage(err.message, true);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    initializeSessionAndFetch();

    // Cleanup function
    return () => {
      isMounted = false;
      if (supabase && channel) {
        supabase
          .removeChannel(channel)
          .then(() => console.log("Realtime channel unsubscribed."));
      }
    };
  }, [
    user, // This is the key dependency.
    setSessionId,
    setMessages,
    setIsLoading,
    addMessage,
    updateMessage,
    removeMessage,
    addSystemMessage,
  ]);

  return { user }; // Return the auth user
};