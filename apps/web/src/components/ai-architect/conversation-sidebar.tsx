"use client";

import type { AIThread } from "@compose-ai/shared";
import { Archive, MessageSquareText, Plus } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface ConversationSidebarProps {
  activeThreadId: string | null;
  archived: boolean;
  busy: boolean;
  loading: boolean;
  onArchive: (thread: AIThread) => void;
  onCreate: () => void;
  onSelect: (threadId: string) => void;
  threads: AIThread[];
}

export function ConversationSidebar({
  activeThreadId,
  archived,
  busy,
  loading,
  onArchive,
  onCreate,
  onSelect,
  threads,
}: ConversationSidebarProps) {
  const reducedMotion = useReducedMotion();

  return (
    <aside
      aria-label="AI Architect conversations"
      className="flex min-h-[660px] flex-col border-r border-slate-200 bg-[#fbfcfe] xl:h-[max(620px,calc(100dvh-13rem))] xl:min-h-0 xl:max-h-[840px]"
    >
      <div className="flex min-h-[72px] items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Conversations</h2>
          <p className="mt-0.5 text-xs text-slate-500">Project history</p>
        </div>
        <Button
          aria-label="New conversation"
          className="size-9 border-slate-200 bg-white text-violet-700 shadow-sm hover:bg-violet-50"
          disabled={archived || busy}
          onClick={onCreate}
          size="icon"
          title="New conversation"
          variant="outline"
        >
          <Plus aria-hidden="true" />
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2" data-architect-scroll>
        {loading ? (
          <div className="divide-y divide-slate-100 px-1" role="status" aria-label="Loading conversations">
            {Array.from({ length: 5 }, (_, index) => (
              <div className="space-y-2 px-2 py-3.5" key={index}>
                <Skeleton className="h-3.5 w-4/5 bg-slate-200" />
                <Skeleton className="h-3 w-2/5 bg-slate-100" />
              </div>
            ))}
          </div>
        ) : null}

        {!loading && !threads.length ? (
          <div className="px-3 py-12 text-center">
            <span className="mx-auto flex size-10 items-center justify-center rounded-md border border-violet-100 bg-violet-50 text-violet-700">
              <MessageSquareText aria-hidden="true" className="size-[18px]" />
            </span>
            <p className="mt-4 text-sm font-semibold text-slate-900">No conversations yet</p>
            <p className="mt-1.5 text-xs leading-5 text-slate-500">
              Start a focused thread for project questions or brief clarification.
            </p>
            <Button
              className="mt-5 border-violet-200 bg-white text-violet-700 hover:bg-violet-50"
              disabled={archived || busy}
              onClick={onCreate}
              size="sm"
              variant="outline"
            >
              <Plus aria-hidden="true" />
              New conversation
            </Button>
          </div>
        ) : null}

        <ol className="divide-y divide-slate-100">
          {threads.map((thread, index) => {
            const active = thread.id === activeThreadId;
            return (
              <motion.li
                animate={{ opacity: 1, x: 0 }}
                className="group relative"
                initial={reducedMotion ? false : { opacity: 0, x: -5 }}
                key={thread.id}
                transition={{ delay: Math.min(index * 0.025, 0.15), duration: 0.22 }}
              >
                <button
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative w-full rounded-md px-3 py-3 pr-10 text-left outline-none transition-colors hover:bg-slate-100/80 focus-visible:ring-2 focus-visible:ring-violet-500/50",
                    active &&
                      "bg-violet-50/90 text-violet-950 before:absolute before:bottom-2 before:left-0 before:top-2 before:w-0.5 before:rounded-full before:bg-violet-600",
                  )}
                  onClick={() => onSelect(thread.id)}
                  type="button"
                >
                  <span className="block truncate text-sm font-medium text-slate-800">
                    {thread.title}
                  </span>
                  <span className="mt-1.5 flex items-center gap-1.5 text-[11px] text-slate-500">
                    <span>
                      {thread.messageCount} {thread.messageCount === 1 ? "message" : "messages"}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>{formatThreadDate(thread.lastMessageAt ?? thread.createdAt)}</span>
                  </span>
                </button>
                <Button
                  aria-label={`Archive ${thread.title}`}
                  className="absolute right-1.5 top-2 size-8 text-slate-400 opacity-100 hover:bg-white hover:text-slate-700 sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100"
                  disabled={archived || busy}
                  onClick={() => onArchive(thread)}
                  size="icon"
                  title="Archive conversation"
                  variant="ghost"
                >
                  <Archive aria-hidden="true" />
                </Button>
              </motion.li>
            );
          })}
        </ol>
      </div>
    </aside>
  );
}

function formatThreadDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Recent";
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(date);
}
