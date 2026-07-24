"use client";

import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface PublicVisualShellProps {
  children: React.ReactNode;
  className?: string;
}

interface FloatingArtifactProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  distance?: number;
}

export function PublicVisualShell({ children, className }: PublicVisualShellProps) {
  const reducedMotion = useReducedMotion();
  const pointerX = useMotionValue(-600);
  const pointerY = useMotionValue(-600);
  const glowX = useSpring(pointerX, { damping: 34, mass: 0.35, stiffness: 190 });
  const glowY = useSpring(pointerY, { damping: 34, mass: 0.35, stiffness: 190 });
  const glow = useMotionTemplate`radial-gradient(560px circle at ${glowX}px ${glowY}px, rgb(126 105 255 / 0.16), rgb(76 148 255 / 0.07) 38%, transparent 72%)`;

  const handlePointerMove = React.useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (reducedMotion || event.pointerType === "touch") return;
      const bounds = event.currentTarget.getBoundingClientRect();
      pointerX.set(event.clientX - bounds.left);
      pointerY.set(event.clientY - bounds.top);
    },
    [pointerX, pointerY, reducedMotion],
  );

  const handlePointerLeave = React.useCallback(() => {
    pointerX.set(-600);
    pointerY.set(-600);
  }, [pointerX, pointerY]);

  return (
    <div
      className={cn("compose-public-light relative isolate overflow-x-clip", className)}
      onPointerLeave={handlePointerLeave}
      onPointerMove={handlePointerMove}
    >
      <div aria-hidden="true" className="compose-public-grid pointer-events-none absolute inset-0" />
      <motion.div
        aria-hidden="true"
        className="compose-pointer-glow pointer-events-none absolute inset-0"
        style={{ background: glow }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}

export function FloatingArtifact({
  children,
  className,
  delay = 0,
  distance = 8,
}: FloatingArtifactProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      animate={
        reducedMotion
          ? undefined
          : {
              rotate: [0, 0.6, 0],
              y: [0, -distance, 0],
            }
      }
      className={className}
      transition={{
        delay,
        duration: 5.5 + delay,
        ease: "easeInOut",
        repeat: Infinity,
      }}
    >
      {children}
    </motion.div>
  );
}
