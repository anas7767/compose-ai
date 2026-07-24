"use client";

import { SignedIn, SignedOut } from "@clerk/nextjs";
import {
  ArrowRight,
  BadgeCheck,
  BrainCircuit,
  Compass,
  Layers3,
  MoveUpRight,
  ScanLine,
  Sparkles,
  Waypoints,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import * as React from "react";

import { PublicBrand } from "@/components/public/public-brand";
import {
  FloatingArtifact,
  PublicVisualShell,
} from "@/components/public/public-visual-shell";

const easeOut = [0.22, 1, 0.36, 1] as const;

const workflow = [
  {
    number: "01",
    title: "Understand the plot",
    description: "Capture geometry, access, orientation, and buildable potential in one site profile.",
    icon: Compass,
  },
  {
    number: "02",
    title: "Compose the brief",
    description: "Turn conversations and constraints into an approved, structured design intent.",
    icon: BrainCircuit,
  },
  {
    number: "03",
    title: "Explore concepts",
    description: "Compare traceable floor-plan directions instead of settling for the first answer.",
    icon: Waypoints,
  },
  {
    number: "04",
    title: "Preserve decisions",
    description: "Accept a concept into a versioned project record that remains explainable.",
    icon: Layers3,
  },
];

const capabilities = [
  {
    eyebrow: "Site intelligence",
    title: "Begin with what the land allows.",
    description:
      "Plot geometry, road access, orientation, and feasibility stay connected to every later decision.",
    icon: ScanLine,
  },
  {
    eyebrow: "Project memory",
    title: "A brief that gets sharper over time.",
    description:
      "Requirements, constraints, clarifications, and approvals build a reliable memory for the project.",
    icon: BrainCircuit,
  },
  {
    eyebrow: "Concept generation",
    title: "Options with reasons, not mystery.",
    description:
      "Conceptual plans carry validation results, constraint traces, and the thinking behind major choices.",
    icon: Sparkles,
  },
];

function BlueprintMiniature() {
  return (
    <div className="compose-blueprint-sheet" role="img" aria-label="Abstract architectural floor plan">
      <div className="compose-blueprint-room left-[10%] top-[12%] h-[34%] w-[38%]" />
      <div className="compose-blueprint-room right-[10%] top-[12%] h-[52%] w-[34%]" />
      <div className="compose-blueprint-room bottom-[10%] left-[10%] h-[34%] w-[54%]" />
      <span className="absolute bottom-3 right-3 text-[9px] font-semibold uppercase text-violet-500">
        1:100
      </span>
    </div>
  );
}

function WorkspaceLink() {
  return (
    <>
      <SignedOut>
        <Link
          className="compose-primary-action group"
          href="/sign-in"
        >
          Enter Compose
          <ArrowRight
            aria-hidden="true"
            className="size-4 transition-transform duration-300 group-hover:translate-x-0.5"
          />
        </Link>
      </SignedOut>
      <SignedIn>
        <Link className="compose-primary-action group" href="/dashboard">
          Open workspace
          <ArrowRight
            aria-hidden="true"
            className="size-4 transition-transform duration-300 group-hover:translate-x-0.5"
          />
        </Link>
      </SignedIn>
    </>
  );
}

export function LandingPage() {
  const reducedMotion = useReducedMotion();
  const [imageLoaded, setImageLoaded] = React.useState(false);
  const initial = reducedMotion ? false : { opacity: 0, y: 18 };

  return (
    <PublicVisualShell className="min-h-dvh bg-[#f7f8fc] text-slate-950">
      <motion.div
        animate={{ opacity: 1 }}
        initial={reducedMotion ? false : { opacity: 0 }}
        transition={{ duration: 0.5, ease: easeOut }}
      >
        <header className="compose-public-nav relative z-50 mx-auto flex h-20 w-full max-w-[1480px] items-center justify-between px-5 sm:px-8 lg:px-12">
          <PublicBrand />
          <nav aria-label="Public navigation" className="hidden items-center gap-7 md:flex">
            <a className="compose-public-nav-link" href="#workflow">
              Workflow
            </a>
            <a className="compose-public-nav-link" href="#capabilities">
              Platform
            </a>
            <a className="compose-public-nav-link" href="#principles">
              Principles
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <SignedOut>
              <Link className="compose-secondary-action hidden sm:inline-flex" href="/sign-in">
                Sign in
              </Link>
            </SignedOut>
            <WorkspaceLink />
          </div>
        </header>

        <main>
          <section className="relative mx-auto flex min-h-[720px] w-full max-w-[1480px] items-center overflow-hidden px-5 pb-28 pt-10 sm:min-h-[700px] sm:px-8 sm:pb-32 lg:min-h-[max(660px,calc(100svh-9rem))] lg:px-12 lg:pt-0">
            <div
              aria-busy={!imageLoaded}
              className="compose-hero-art pointer-events-none absolute inset-0"
            >
              <div
                aria-hidden="true"
                className={`compose-image-loading absolute inset-0 transition-opacity duration-700 ${
                  imageLoaded ? "opacity-0" : "opacity-100"
                }`}
              />
              <Image
                alt="Isometric cutaway model of a contemporary house and landscaped plot"
                className={`compose-hero-image object-contain transition-[opacity,transform] duration-1000 ${
                  imageLoaded ? "scale-100 opacity-100" : "scale-[1.015] opacity-0"
                }`}
                fill
                onLoad={() => setImageLoaded(true)}
                priority
                sizes="(max-width: 768px) 140vw, 100vw"
                src="/images/compose-architecture-hero.png"
              />
            </div>

            <div className="relative z-20 max-w-[670px] pt-3 sm:pt-0">
              <motion.div
                animate={{ opacity: 1, y: 0 }}
                className="mb-7 inline-flex items-center gap-2 rounded-full border border-violet-200/80 bg-white/72 px-3 py-1.5 text-xs font-semibold text-violet-700 shadow-[0_8px_28px_rgb(98_79_180_/_0.1)] backdrop-blur-xl"
                initial={initial}
                transition={{ delay: 0.05, duration: 0.55, ease: easeOut }}
              >
                <Sparkles aria-hidden="true" className="size-3.5" />
                Building intelligence, composed
              </motion.div>

              <motion.h1
                animate={{ opacity: 1, y: 0 }}
                className="text-6xl font-semibold leading-[0.88] text-slate-950 sm:text-7xl lg:text-[7.25rem]"
                initial={initial}
                transition={{ delay: 0.11, duration: 0.65, ease: easeOut }}
              >
                Compose AI
              </motion.h1>
              <motion.p
                animate={{ opacity: 1, y: 0 }}
                className="mt-5 max-w-[610px] text-3xl font-medium leading-[1.05] text-slate-800 sm:text-4xl lg:text-5xl"
                initial={initial}
                transition={{ delay: 0.17, duration: 0.65, ease: easeOut }}
              >
                Architecture, composed with intelligence.
              </motion.p>
              <motion.p
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 max-w-[560px] text-base leading-7 text-slate-600 sm:text-lg sm:leading-8"
                initial={initial}
                transition={{ delay: 0.23, duration: 0.65, ease: easeOut }}
              >
                Bring plot intelligence, project requirements, and conceptual floor plans into one
                clear, collaborative design workspace.
              </motion.p>

              <motion.div
                animate={{ opacity: 1, y: 0 }}
                className="mt-8 flex flex-wrap items-center gap-3"
                initial={initial}
                transition={{ delay: 0.29, duration: 0.65, ease: easeOut }}
              >
                <WorkspaceLink />
                <a className="compose-secondary-action group" href="#workflow">
                  See the workflow
                  <MoveUpRight
                    aria-hidden="true"
                    className="size-4 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                  />
                </a>
              </motion.div>

              <motion.ul
                animate={{ opacity: 1 }}
                className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-600"
                initial={reducedMotion ? false : { opacity: 0 }}
                transition={{ delay: 0.38, duration: 0.6 }}
              >
                {["Concept-first", "Versioned decisions", "Human approved"].map((item) => (
                  <li className="inline-flex items-center gap-2" key={item}>
                    <BadgeCheck aria-hidden="true" className="size-4 text-emerald-600" />
                    {item}
                  </li>
                ))}
              </motion.ul>
            </div>

            <div aria-hidden="true" className="absolute inset-0 z-10 hidden lg:block">
              <FloatingArtifact className="absolute right-[6%] top-[13%]" delay={0.2}>
                <BlueprintMiniature />
              </FloatingArtifact>
              <FloatingArtifact className="absolute right-[4%] top-[54%]" delay={0.8} distance={7}>
                <div className="compose-floating-status w-[205px]">
                  <span className="flex size-8 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
                    <BadgeCheck className="size-4" />
                  </span>
                  <span>
                    <span className="block text-[11px] font-medium text-slate-500">Plot profile</span>
                    <span className="mt-0.5 block text-sm font-semibold text-slate-900">
                      Ready for briefing
                    </span>
                  </span>
                </div>
              </FloatingArtifact>
              <FloatingArtifact className="absolute bottom-[16%] right-[28%]" delay={1.4} distance={6}>
                <div className="compose-floating-status w-[192px]">
                  <span className="flex size-8 items-center justify-center rounded-md bg-violet-50 text-violet-700">
                    <Waypoints className="size-4" />
                  </span>
                  <span>
                    <span className="block text-[11px] font-medium text-slate-500">Concept set</span>
                    <span className="mt-0.5 block text-sm font-semibold text-slate-900">
                      3 distinct directions
                    </span>
                  </span>
                </div>
              </FloatingArtifact>
            </div>

            <div className="absolute inset-x-5 bottom-6 z-20 sm:inset-x-8 lg:inset-x-12">
              <div className="mx-auto grid max-w-[1400px] grid-cols-3 border-y border-slate-200/80 bg-white/55 backdrop-blur-lg">
                {[
                  ["Plot", "Measured"],
                  ["Brief", "Aligned"],
                  ["Concepts", "Traceable"],
                ].map(([label, value], index) => (
                  <div
                    className={`px-3 py-3.5 sm:px-5 ${index > 0 ? "border-l border-slate-200/80" : ""}`}
                    key={label}
                  >
                    <span className="block text-[10px] font-semibold uppercase text-slate-400 sm:text-[11px]">
                      {label}
                    </span>
                    <span className="mt-0.5 block text-xs font-semibold text-slate-800 sm:text-sm">
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section
            className="border-y border-slate-200/80 bg-white/88 py-20 sm:py-24"
            id="workflow"
          >
            <div className="mx-auto max-w-[1400px] px-5 sm:px-8 lg:px-12">
              <div className="max-w-3xl">
                <p className="compose-section-kicker">A connected design process</p>
                <h2 className="mt-4 text-3xl font-semibold leading-tight text-slate-950 sm:text-5xl">
                  From site facts to a concept worth developing.
                </h2>
              </div>
              <div className="mt-14 grid border-t border-slate-200 md:grid-cols-2 lg:grid-cols-4">
                {workflow.map((item, index) => {
                  const Icon = item.icon;
                  return (
                    <motion.article
                      className={`relative min-h-[275px] border-b border-slate-200 px-1 py-8 md:px-6 lg:border-b-0 ${
                        index > 0 ? "lg:border-l" : ""
                      }`}
                      initial={reducedMotion ? false : { opacity: 0, y: 20 }}
                      key={item.number}
                      transition={{ delay: index * 0.07, duration: 0.55, ease: easeOut }}
                      viewport={{ amount: 0.35, once: true }}
                      whileInView={{ opacity: 1, y: 0 }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-violet-600">{item.number}</span>
                        <Icon aria-hidden="true" className="size-5 text-slate-400" strokeWidth={1.6} />
                      </div>
                      <h3 className="mt-14 text-xl font-semibold text-slate-950">{item.title}</h3>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{item.description}</p>
                    </motion.article>
                  );
                })}
              </div>
            </div>
          </section>

          <section className="bg-[#f7f8fc] py-20 sm:py-28" id="capabilities">
            <div className="mx-auto max-w-[1400px] px-5 sm:px-8 lg:px-12">
              <div className="grid gap-12 lg:grid-cols-[0.75fr_1.25fr] lg:gap-20">
                <div className="lg:sticky lg:top-24 lg:self-start">
                  <p className="compose-section-kicker">One project intelligence layer</p>
                  <h2 className="mt-4 text-3xl font-semibold leading-tight text-slate-950 sm:text-5xl">
                    Context stays attached to the architecture.
                  </h2>
                  <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
                    Compose keeps the site, brief, constraints, and conceptual options in the same
                    decision history, ready for the people responsible for the project.
                  </p>
                </div>
                <div className="grid gap-4" id="principles">
                  {capabilities.map((item, index) => {
                    const Icon = item.icon;
                    return (
                      <motion.article
                        className="compose-capability-card group"
                        initial={reducedMotion ? false : { opacity: 0, x: 24 }}
                        key={item.eyebrow}
                        transition={{ delay: index * 0.08, duration: 0.55, ease: easeOut }}
                        viewport={{ amount: 0.35, once: true }}
                        whileHover={reducedMotion ? undefined : { y: -3 }}
                        whileInView={{ opacity: 1, x: 0 }}
                      >
                        <span className="flex size-11 shrink-0 items-center justify-center rounded-md border border-violet-100 bg-violet-50/80 text-violet-700 transition-colors duration-300 group-hover:bg-violet-100/80">
                          <Icon aria-hidden="true" className="size-5" strokeWidth={1.7} />
                        </span>
                        <div>
                          <p className="text-xs font-semibold uppercase text-violet-600">
                            {item.eyebrow}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-slate-950 sm:text-2xl">
                            {item.title}
                          </h3>
                          <p className="mt-3 text-sm leading-6 text-slate-600 sm:text-base sm:leading-7">
                            {item.description}
                          </p>
                        </div>
                      </motion.article>
                    );
                  })}
                </div>
              </div>
            </div>
          </section>

          <section className="border-t border-slate-200 bg-white py-20 sm:py-24">
            <div className="mx-auto flex max-w-[1400px] flex-col items-start justify-between gap-8 px-5 sm:px-8 lg:flex-row lg:items-end lg:px-12">
              <div className="max-w-3xl">
                <p className="compose-section-kicker">Begin with clarity</p>
                <h2 className="mt-4 text-3xl font-semibold leading-tight text-slate-950 sm:text-5xl">
                  Give every building idea a stronger first decision.
                </h2>
              </div>
              <WorkspaceLink />
            </div>
          </section>
        </main>

        <footer className="border-t border-slate-200 bg-white py-8">
          <div className="mx-auto flex max-w-[1400px] flex-col gap-4 px-5 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
            <PublicBrand />
            <p>Conceptual building intelligence for better design conversations.</p>
          </div>
        </footer>
      </motion.div>
    </PublicVisualShell>
  );
}
