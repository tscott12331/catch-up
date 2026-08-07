"use client";

import type { SubmitEvent } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRepository } from "../_lib/api";
import { repositoryPathname } from "../_lib/repository";
import { Brand } from "./brand";
import { Icon } from "./icon";
import styles from "./landing.module.css";

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
    <main className={styles.landingShell}>
      <div className={styles.landingTopbar}>
        <Brand />
        <span className={styles.topbarNote}>Repository intelligence, locally</span>
      </div>

      <section className={styles.landingContent}>
        <div className={styles.eyebrow}><span className={styles.eyebrowDot} /> Codebase onboarding assistant</div>
        <h1>Get oriented in any<br /><em>codebase.</em></h1>
        <p className={styles.landingCopy}>Ask questions, trace behavior, and find your way around unfamiliar repositories — with every answer grounded in source.</p>
        <form className={styles.repoForm} onSubmit={submit}>
          <label htmlFor="repository-url">Repository URL</label>
          <div className={styles.urlInputWrap}>
            <Icon name="github" size={18} />
            <input id="repository-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repository" autoComplete="url" />
            <button className={styles.connectButton} type="submit" disabled={isConnecting}>{isConnecting ? "Connecting…" : "Connect"} {!isConnecting && <Icon name="arrow-up" size={15} />}</button>
          </div>
          {error ? <p className={styles.formError}>{error}</p> : <p className={styles.formHint}>Public GitHub repositories are supported in this first version.</p>}
        </form>
        <button className={styles.demoLink} onClick={tryDemo} disabled={isConnecting}>Try the demo repository <span>↗</span></button>
      </section>

      <div className={styles.landingFooter}>
        <span><Icon name="check" size={14} /> Read-only by design</span>
        <span>Phase 01 · Foundation</span>
      </div>
    </main>
  );
}
