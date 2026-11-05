"use client";

import Image from "next/image";
import { useRef } from "react";
import type { PointerEvent } from "react";
import { ArrowDownRight } from "lucide-react";

export function HeroArt() {
  const art = useRef<HTMLDivElement>(null);
  function move(event: PointerEvent<HTMLDivElement>) {
    if (
      event.pointerType !== "mouse" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const box = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    art.current?.style.setProperty("--art-x", `${x * 8}px`);
    art.current?.style.setProperty("--art-y", `${y * 8}px`);
  }
  function reset() {
    art.current?.style.setProperty("--art-x", "0px");
    art.current?.style.setProperty("--art-y", "0px");
  }
  return (
    <div className="hero-art" onPointerMove={move} onPointerLeave={reset}>
      <div className="sculpture-wrap" ref={art}>
        <Image
          src="/art/cairn-cutout.webp"
          alt="Three sculptural basalt stones balanced over a precise red layer, a cairn marking a checked path."
          width={1122}
          height={1402}
          sizes="(max-width: 700px) 100vw, 55vw"
          preload
          className="sculpture"
        />
      </div>
      <a className="art-case-link" href="#investigation">
        <span>
          <span className="case-link-caption">Explore a recorded case</span>
          Northstar Diagnostics
        </span>
        <span className="case-link-arrow">
          <ArrowDownRight size={23} />
        </span>
      </a>
    </div>
  );
}
