"use client";

import type { AIMessage, AIMessageMode, AISuggestedPrompt } from "@compose-ai/shared";
import {
  ArrowUpRight,
  Bot,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  UserRound,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface ChatPanelProps {
  archived: boolean;
  draft: string;
  loading: boolean;
  messages: AIMessage[];
  mode: AIMessageMode;
  onDraftChange: (value: string) => void;
  onModeChange: (mode: AIMessageMode) => void;
  onSend: () => void;
  onStop: () => void;
  onUsePrompt: (prompt: AISuggestedPrompt) => void;
  sending: boolean;
  streamingContent: string;
  suggestions: AISuggestedPrompt[];
  threadSelected: boolean;
}

export function ChatPanel({
  archived,
  draft,
  loading,
  messages,
  mode,
  onDraftChange,
  onModeChange,
  onSend,
  onStop,
  onUsePrompt,
  sending,
  streamingContent,
  suggestions,
  threadSelected,
}: ChatPanelProps) {
  const endRef = React.useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();

  React.useEffect(() => {
    endRef.current?.scrollIntoView({
      block: "end",
      behavior: reducedMotion || streamingContent ? "auto" : "smooth",
    });
  }, [messages, reducedMotion, streamingContent]);

  const submit = () => {
    if (!draft.trim() || sending || archived) return;
    onSend();
  };

  return (
    <section className="flex min-h-[660px] min-w-0 flex-col bg-white xl:h-[max(620px,calc(100dvh-13rem))] xl:min-h-0 xl:max-h-[840px]">
      <div className="flex min-h-[72px] flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
            Design conversation
          </h2>
          <p className="mt-0.5 truncate text-xs text-slate-500">
            Project and plot context included
          </p>
        </div>
        <div
          aria-label="Conversation mode"
          className="grid grid-cols-2 rounded-md border border-slate-200 bg-slate-100 p-0.5"
          role="group"
        >
          {(["advice", "proposal"] as const).map((value) => (
            <button
              aria-pressed={mode === value}
              className={cn(
                "h-8 rounded px-3 text-xs font-medium text-slate-500 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-violet-500/50",
                mode === value && "bg-white text-slate-900 shadow-sm",
              )}
              disabled={archived || sending}
              key={value}
              onClick={() => onModeChange(value)}
              type="button"
            >
              {value === "advice" ? "Advice" : "Propose"}
            </button>
          ))}
        </div>
      </div>

      <div
        aria-busy={sending}
        aria-live="polite"
        className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6"
        data-architect-scroll
      >
        {loading ? (
          <div className="mx-auto max-w-3xl space-y-7" role="status" aria-label="Loading messages">
            <div className="flex gap-3">
              <Skeleton className="size-8 shrink-0 bg-slate-200" />
              <div className="flex-1 space-y-2 pt-1">
                <Skeleton className="h-3 w-24 bg-slate-200" />
                <Skeleton className="h-3 w-4/5 bg-slate-100" />
                <Skeleton className="h-3 w-3/5 bg-slate-100" />
              </div>
            </div>
            <Skeleton className="ml-auto h-20 w-2/3 bg-violet-50" />
          </div>
        ) : null}

        {!loading && !threadSelected ? (
          <ChatEmptyState
            archived={archived}
            onUsePrompt={onUsePrompt}
            suggestions={suggestions}
          />
        ) : null}

        {!loading && threadSelected && !messages.length && !streamingContent ? (
          <ChatEmptyState
            archived={archived}
            onUsePrompt={onUsePrompt}
            suggestions={suggestions}
          />
        ) : null}

        <ol className="mx-auto max-w-3xl space-y-7">
          {messages.map((message) => (
            <MessageRow key={message.id} message={message} reducedMotion={Boolean(reducedMotion)} />
          ))}
          {sending ? (
            <StreamingMessage
              content={streamingContent}
              onStop={onStop}
              reducedMotion={Boolean(reducedMotion)}
            />
          ) : null}
        </ol>
        <div ref={endRef} />
      </div>

      <div className="border-t border-slate-200 bg-[#fbfcfe] px-3 py-3 sm:px-6 sm:py-4">
        <div className="mx-auto max-w-3xl">
          <label className="sr-only" htmlFor="architect-message">
            Message AI Architect
          </label>
          <div className="overflow-hidden rounded-lg border border-slate-300 bg-white shadow-[0_8px_28px_rgb(51_65_85_/_0.08)] transition-[border-color,box-shadow] focus-within:border-violet-400 focus-within:shadow-[0_8px_30px_rgb(109_70_215_/_0.11)]">
            <Textarea
              className="min-h-20 max-h-44 resize-none border-0 bg-transparent px-3.5 py-3 text-[15px] leading-6 shadow-none focus-visible:border-0 focus-visible:ring-0"
              disabled={archived || sending}
              id="architect-message"
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit();
                }
              }}
              placeholder={
                archived
                  ? "Restore this project to continue the conversation."
                  : "Ask about priorities, requirements, or site constraints..."
              }
              value={draft}
            />
            <div className="flex min-h-12 items-center justify-between gap-3 border-t border-slate-100 px-2.5 py-2">
              <span className="inline-flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
                <ShieldCheck aria-hidden="true" className="size-3.5 shrink-0 text-violet-600" />
                <span className="truncate">
                  {mode === "advice" ? "Read-only guidance" : "Changes require approval"}
                </span>
              </span>
              <Button
                aria-label={sending ? "Stop response" : "Send message"}
                className={cn(
                  "size-9 shrink-0",
                  !sending && "bg-violet-600 text-white hover:bg-violet-700",
                )}
                disabled={!sending && (!draft.trim() || archived)}
                onClick={sending ? onStop : submit}
                size="icon"
                title={sending ? "Stop response" : "Send message"}
                type="button"
                variant={sending ? "outline" : "default"}
              >
                {sending ? <Square aria-hidden="true" /> : <Send aria-hidden="true" />}
              </Button>
            </div>
          </div>
          <p className="mt-2 px-1 text-[11px] leading-4 text-slate-500">
            AI output may be incomplete. Review evidence and confidence before approval.
          </p>
        </div>
      </div>
    </section>
  );
}

function MessageRow({
  message,
  reducedMotion,
}: {
  message: AIMessage;
  reducedMotion: boolean;
}) {
  const user = message.role === "user";
  return (
    <motion.li
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex gap-3", user && "flex-row-reverse")}
      initial={reducedMotion ? false : { opacity: 0, y: 6 }}
      transition={{ duration: 0.22 }}
    >
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-md border shadow-sm",
          user
            ? "border-slate-200 bg-white text-slate-600"
            : "border-violet-200 bg-violet-50 text-violet-700",
        )}
      >
        {user ? (
          <UserRound aria-hidden="true" className="size-4" />
        ) : (
          <Bot aria-hidden="true" className="size-4" />
        )}
      </div>
      <div
        className={cn(
          "min-w-0 max-w-[88%] text-sm leading-6 text-slate-700",
          user
            ? "rounded-lg border border-violet-100 bg-violet-50/70 px-3.5 py-2.5 text-slate-800"
            : "flex-1 pt-0.5",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        <p className="mt-1.5 text-[11px] capitalize text-slate-400">
          {message.status === "failed" ? "Response interrupted" : message.mode}
        </p>
      </div>
    </motion.li>
  );
}

function StreamingMessage({
  content,
  onStop,
  reducedMotion,
}: {
  content: string;
  onStop: () => void;
  reducedMotion: boolean;
}) {
  return (
    <motion.li
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3"
      initial={reducedMotion ? false : { opacity: 0, y: 6 }}
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-violet-200 bg-violet-50 text-violet-700 shadow-sm">
        <Bot aria-hidden="true" className="size-4" />
      </div>
      <div className="min-w-0 flex-1 pt-0.5 text-sm leading-6 text-slate-700">
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-xs font-medium text-slate-500">AI Architect is responding</p>
          <Button
            className="h-7 border-slate-200 px-2 text-[11px] text-slate-600"
            onClick={onStop}
            size="sm"
            variant="outline"
          >
            <Square aria-hidden="true" className="size-3" />
            Stop
          </Button>
        </div>
        {content ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="flex items-center gap-2 text-slate-500">
            <span className="flex items-center gap-1" aria-hidden="true">
              {[0, 1, 2].map((index) => (
                <motion.span
                  animate={
                    reducedMotion
                      ? undefined
                      : { opacity: [0.35, 1, 0.35], y: [0, -2, 0] }
                  }
                  className="size-1.5 rounded-full bg-violet-500"
                  key={index}
                  transition={{ delay: index * 0.14, duration: 0.9, repeat: Infinity }}
                />
              ))}
            </span>
            Reviewing project context
          </div>
        )}
      </div>
    </motion.li>
  );
}

function ChatEmptyState({
  archived,
  onUsePrompt,
  suggestions,
}: {
  archived: boolean;
  onUsePrompt: (prompt: AISuggestedPrompt) => void;
  suggestions: AISuggestedPrompt[];
}) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-10 text-center sm:py-14">
      <span className="flex size-11 items-center justify-center rounded-md border border-violet-200 bg-violet-50 text-violet-700 shadow-sm">
        <Sparkles aria-hidden="true" className="size-5" />
      </span>
      <h3 className="mt-4 text-base font-semibold text-slate-900">Start with the project brief</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
        Ask a focused question or use a suggested prompt. Compose uses the current project and plot
        context while keeping every proposed change under your control.
      </p>
      {suggestions.length ? (
        <div className="mt-7 w-full divide-y divide-slate-200 border-y border-slate-200 text-left">
          {suggestions.map((prompt) => (
            <button
              className="group flex min-h-12 w-full items-center gap-3 px-1 py-2.5 text-sm font-medium text-slate-700 outline-none transition-colors hover:text-violet-700 focus-visible:bg-violet-50 focus-visible:ring-2 focus-visible:ring-violet-500/40 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={archived}
              key={prompt.id}
              onClick={() => onUsePrompt(prompt)}
              type="button"
            >
              <Sparkles aria-hidden="true" className="size-4 shrink-0 text-violet-500" />
              <span className="min-w-0 flex-1">{prompt.label}</span>
              <span className="text-[11px] capitalize text-slate-400">{prompt.mode}</span>
              <ArrowUpRight
                aria-hidden="true"
                className="size-4 shrink-0 text-slate-400 transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
              />
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
