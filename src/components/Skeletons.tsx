import React from "react";

/**
 * A skeleton loader for a single chat message.
 */
const MessageSkeleton: React.FC<{ isUser?: boolean }> = ({ isUser = false }) => (
  <div
    className={`flex items-end gap-2 p-3 ${
      isUser ? "justify-end" : "justify-start"
    }`}
  >
    {!isUser && (
      <div className="w-8 h-8 rounded-full bg-slate-700 flex-shrink-0 animate-pulse" />
    )}
    <div
      className={`w-2/5 h-12 rounded-xl bg-slate-700 animate-pulse ${
        isUser ? "rounded-br-lg" : "rounded-bl-lg"
      }`}
    />
    {isUser && (
      <div className="w-8 h-8 rounded-full bg-slate-700 flex-shrink-0 animate-pulse" />
    )}
  </div>
);

/**
 * A skeleton loader for the chat list.
 */
export const ChatListSkeleton: React.FC = () => (
  <div className="flex-1 h-0 overflow-y-auto p-4">
    <MessageSkeleton />
    <MessageSkeleton isUser />
    <MessageSkeleton />
    <MessageSkeleton isUser />
  </div>
);
