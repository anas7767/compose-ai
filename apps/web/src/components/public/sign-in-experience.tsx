"use client";

import { ClerkLoaded, ClerkLoading, SignIn } from "@clerk/nextjs";
import { ArrowLeft, BadgeCheck, LockKeyhole, Sparkles } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import Link from "next/link";

import { PublicBrand } from "@/components/public/public-brand";
import {
  FloatingArtifact,
  PublicVisualShell,
} from "@/components/public/public-visual-shell";

const easeOut = [0.22, 1, 0.36, 1] as const;

function SignInLoadingState() {
  return (
    <div aria-label="Loading sign in" className="compose-auth-loading" role="status">
      <div className="mx-auto h-7 w-36 rounded bg-slate-200/80" />
      <div className="mx-auto mt-3 h-4 w-48 rounded bg-slate-100" />
      <div className="mt-8 h-11 rounded-md bg-slate-100" />
      <div className="my-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-slate-200" />
        <div className="h-3 w-8 rounded bg-slate-100" />
        <div className="h-px flex-1 bg-slate-200" />
      </div>
      <div className="h-4 w-20 rounded bg-slate-100" />
      <div className="mt-2 h-11 rounded-md bg-slate-100" />
      <div className="mt-5 h-11 rounded-md bg-violet-200/70" />
      <span className="sr-only">Preparing secure sign in</span>
    </div>
  );
}

function ArchitecturalSketch() {
  return (
    <div className="compose-auth-sketch" aria-hidden="true">
      <span className="absolute left-[9%] top-[12%] h-[35%] w-[42%] border border-violet-400/50" />
      <span className="absolute right-[9%] top-[12%] h-[56%] w-[35%] border border-blue-400/45" />
      <span className="absolute bottom-[11%] left-[9%] h-[34%] w-[58%] border border-violet-400/50" />
      <span className="absolute bottom-3 right-3 text-[9px] font-semibold uppercase text-violet-600">
        Concept 03
      </span>
    </div>
  );
}

export function SignInExperience() {
  const reducedMotion = useReducedMotion();

  return (
    <PublicVisualShell className="compose-auth-shell min-h-dvh bg-[#f7f8fc] text-slate-950">
      <div aria-hidden="true" className="compose-auth-scene absolute inset-0">
        <Image
          alt=""
          className="compose-auth-scene-image object-cover"
          fill
          priority
          sizes="100vw"
          src="/images/compose-architecture-hero.png"
        />
      </div>

      <header className="absolute inset-x-0 top-0 z-40 mx-auto flex h-20 w-full max-w-[1480px] items-center justify-between px-5 sm:px-8 lg:px-12">
        <PublicBrand />
        <Link className="compose-auth-back group" href="/">
          <ArrowLeft
            aria-hidden="true"
            className="size-4 transition-transform duration-300 group-hover:-translate-x-0.5"
          />
          Back to overview
        </Link>
      </header>

      <main className="relative z-20 mx-auto grid min-h-dvh w-full max-w-[1480px] items-center gap-12 px-5 pb-10 pt-28 sm:px-8 sm:pb-12 lg:grid-cols-[minmax(0,1fr)_460px] lg:px-12">
        <motion.section
          animate={{ opacity: 1, y: 0 }}
          className="hidden max-w-xl self-end pb-16 lg:block"
          initial={reducedMotion ? false : { opacity: 0, y: 18 }}
          transition={{ duration: 0.65, ease: easeOut }}
        >
          <p className="compose-section-kicker">Your architecture workspace</p>
          <h1 className="mt-4 text-5xl font-semibold leading-[1.02] text-slate-950">
            Return to the decisions shaping your project.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
            Continue with your site intelligence, approved brief, and conceptual design history in
            one secure workspace.
          </p>
        </motion.section>

        <motion.section
          animate={{ opacity: 1, scale: 1, y: 0 }}
          aria-label="Sign in to Compose AI"
          className="compose-auth-glass relative mx-auto w-full max-w-[460px]"
          initial={reducedMotion ? false : { opacity: 0, scale: 0.985, y: 20 }}
          transition={{ delay: 0.08, duration: 0.65, ease: easeOut }}
        >
          <div className="mb-6 flex items-center justify-between border-b border-slate-200/80 pb-5">
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600">
              <span className="flex size-8 items-center justify-center rounded-md bg-violet-50 text-violet-700">
                <LockKeyhole aria-hidden="true" className="size-4" />
              </span>
              Secure workspace access
            </span>
            <Sparkles aria-hidden="true" className="size-4 text-violet-500" />
          </div>

          <ClerkLoading>
            <SignInLoadingState />
          </ClerkLoading>
          <ClerkLoaded>
            <SignIn
              fallbackRedirectUrl="/dashboard"
              path="/sign-in"
              routing="path"
              signUpUrl="/sign-up"
            />
          </ClerkLoaded>

          <div className="mt-5 flex items-center justify-center gap-2 border-t border-slate-200/70 pt-5 text-xs text-slate-500">
            <BadgeCheck aria-hidden="true" className="size-3.5 text-emerald-600" />
            Protected by encrypted session management
          </div>
        </motion.section>
      </main>

      <div aria-hidden="true" className="absolute inset-0 z-10 hidden lg:block">
        <FloatingArtifact className="absolute left-[7%] top-[22%]" delay={0.35} distance={6}>
          <ArchitecturalSketch />
        </FloatingArtifact>
      </div>
    </PublicVisualShell>
  );
}
