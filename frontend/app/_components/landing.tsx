"use client";

import type { SubmitEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRepository } from "../_lib/api";
import { repositoryPathname } from "../_lib/repository";
import { Brand } from "./brand";
import { Icon } from "./icon";

export function Landing() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);

  async function connect(repositoryUrl: string) {
    if (isConnecting) return;
    setError("");
    setIsConnecting(true);
    try {
      const response = await createRepository(repositoryUrl);
      router.push(repositoryPathname(response.repository));
    } catch (connectionError) {
      setError(connectionError instanceof Error ? connectionError.message : "The repository could not be connected.");
    } finally {
      setIsConnecting(false);
    }
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    void connect(url.trim());
  }

  function tryDemo() {
    const demoUrl = "https://github.com/acme/checkout-service";
    setUrl(demoUrl);
    void connect(demoUrl);
  }

  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden bg-paper before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(var(--color-pattern)_0.7px,transparent_0.7px)] before:bg-[length:17px_17px] before:opacity-45 before:[mask-image:linear-gradient(to_bottom,transparent,black_25%,black_75%,transparent)]">
      <div className="relative z-1 flex items-center justify-between px-[52px] py-7 max-[760px]:px-5 max-[760px]:py-[22px]">
        <Brand />
        <span className="text-xs tracking-[.03em] text-muted max-[760px]:hidden">Repository intelligence, locally</span>
      </div>

      <section className="relative z-1 m-auto w-[min(680px,calc(100%_-_40px))] py-[56px] pb-[90px] text-center max-[760px]:pt-[45px]">
        <div className="text-[11px] font-bold tracking-[.13em] text-green uppercase"><span className="mr-2 inline-block size-[7px] rounded-full bg-green align-[1px]" /> Codebase onboarding assistant</div>
        <h1 className="my-6 mb-[19px] font-serif text-[clamp(48px,7vw,76px)] leading-[.99] font-normal tracking-[-.055em] max-[430px]:text-[49px]">Get oriented in any<br /><em className="text-green">codebase.</em></h1>
        <p className="mx-auto mb-[42px] max-w-[480px] text-base leading-[1.65] text-landing-copy">Ask questions, trace behavior, and find your way around unfamiliar repositories — with every answer grounded in source.</p>
        <form className="mx-auto max-w-[560px] text-left" onSubmit={submit}>
          <label className="mb-[9px] block text-[11px] font-bold tracking-[.1em] text-label uppercase" htmlFor="repository-url">Repository URL</label>
          <div className="flex items-center gap-3 rounded-xl border border-input-line bg-white py-1.5 pr-[7px] pl-[17px] text-input-icon shadow-landing-input focus-within:border-input-focus focus-within:ring-3 focus-within:ring-green/12 max-[430px]:flex-wrap max-[430px]:py-1.5 max-[430px]:pr-[7px] max-[430px]:pb-[7px] max-[430px]:pl-[13px]">
            <Icon name="github" size={18} />
            <input className="min-w-0 flex-1 border-0 py-2.5 text-sm text-ink outline-0 placeholder:text-placeholder max-[430px]:w-[calc(100%-35px)] max-[430px]:flex-none" id="repository-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repository" autoComplete="url" />
            <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-green px-4 py-[11px] text-[13px] font-bold text-white transition-[background,transform] duration-200 hover:-translate-y-px hover:bg-green-hover disabled:cursor-wait disabled:opacity-65 max-[430px]:w-full" type="submit" disabled={isConnecting}>{isConnecting ? "Connecting…" : "Connect"} {!isConnecting && <Icon name="arrow-up" size={15} />}</button>
          </div>
          {error ? <p className="mx-[3px] mt-2.5 text-xs text-danger">{error}</p> : <p className="mx-[3px] mt-2.5 text-xs text-hint">Public GitHub repositories are supported in this first version.</p>}
        </form>
        <button className="mt-7 border-0 bg-transparent p-0 text-[13px] text-demo hover:text-green disabled:cursor-wait disabled:opacity-65" onClick={tryDemo} disabled={isConnecting}>Try the demo repository <span className="ml-[5px] text-[15px]">↗</span></button>
      </section>

      <div className="relative z-1 flex justify-between border-t border-pattern/75 px-[52px] py-[23px] text-[11px] tracking-[.04em] text-footer max-[760px]:px-5">
        <span className="inline-flex items-center gap-[5px]"><Icon name="check" size={14} /> Read-only by design</span>
        <span className="inline-flex items-center gap-[5px] max-[760px]:hidden">Phase 01 · Foundation</span>
      </div>
    </main>
  );
}
