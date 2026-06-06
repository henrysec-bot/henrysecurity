/**
 * Template for a Dynamic Playbook in the HSEC Agent (Autonomous Security Operations Center).
 * This file illustrates the structure for a specific defense scenario (e.g., Brute Force RDP).
 * Implement the abstract methods to plug in your detection logic, automated responses,
 * and threat‑intelligence enrichment.
 */

import { PlaybookContext, PlaybookResult, ThreatIntelFeed } from './types';

/**
 * Abstract base class that every concrete playbook must extend.
 */
export abstract class BasePlaybook {
  /** Unique identifier for the playbook (used in logging, metrics, etc.) */
  protected readonly id: string;
  /** Human‑readable name */
  protected readonly name: string;
  /** Description of what this playbook detects and mitigates */
  protected readonly description: string;

  constructor(id: string, name: string, description: string) {
    this.id = id;
    this.name = name;
    this.description = description;
  }

  /**
   * Main entry point called by the HSEC Agent engine.
   * @param context – Contains raw log entries, alerts, and any pre‑processed data.
   * @returns A PlaybookResult indicating whether a threat was found and what actions were taken.
   */
  public async execute(context: PlaybookContext): Promise<PlaybookResult> {
    // 1️⃣ Detection / Analysis
    const detection = await this.analyze(context);
    if (!detection.threatDetected) {
      return { playbookId: this.id, threatDetected: false, actions: [], enrichment: [] };
    }

    // 2️⃣ Automated Response (containment, mitigation, notification)
    const actions = await this.respond(context, detection.details);

    // 3️⃣ Threat‑Intel Enrichment (optional but recommended)
    const enrichment = await this.enrich(context, detection.details);

    return {
      playbookId: this.id,
      threatDetected: true,
      actions,
      enrichment,
    };
  }

  /**
   * Analyse the incoming data and decide if the scenario matches.
   * @param context – Input data (logs, alerts, etc.)
   * @returns DetectionResult with a boolean flag and any relevant details.
   */
  protected abstract analyze(context: PlaybookContext): Promise<DetectionResult>;

  /**
   * Define the automated actions to take when a threat is confirmed.
   * This could include: blocking IPs, disabling user accounts, invoking scripts,
   * sending alerts via Telegram/email, creating tickets, etc.
   * @param context – Original input data
   * @param details – Details from the detection phase
   * @returns Array of action descriptors (what was done, status, timestamps).
   */
  protected abstract respond(
    context: PlaybookContext,
    details: any
  ): Promise<Array<ActionResult>>;

  /**
   * Enrich the incident with external threat intelligence.
   * @param context – Original input data
   * @param details – Details from the detection phase
   * @returns Array of enrichment objects (e.g., IOC reputation, geo‑location, MITRE mapping).
   */
  protected abstract enrich(
    context: PlaybookContext,
    details: any
  ): Promise<Array<EnrichmentResult>>;
}

/**
 * Example concrete playbook: Brute Force RDP detection.
 * Replace the logic with your own SIEM / log source queries.
 */
export class RdpBruteForcePlaybook extends BasePlaybook {
  constructor() {
    super(
      'rdp-brute-force',
      'RDP Brute‑Force Detector',
      'Detects repeated failed RDP login attempts from a single source and triggers containment.'
    );
  }

  protected async analyze(context: PlaybookContext): Promise<DetectionResult> {
    // TODO: Implement your detection logic.
    // Example: count EventID 4625 (failed logon) for LogonType 10 (RDP) per source IP in the last 5 min.
    const failedLogins = context.logs
      .filter(
        (e) =>
          e.eventID === 4625 &&
          e.logonType === 10 &&
          e.timestamp > Date.now() - 5 * 60 * 1000
      )
      .reduce((acc, cur) => {
        acc[cur.sourceIP] = (acc[cur.sourceIP] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

    const threshold = 10; // configurable
    for (const [ip, count] of Object.entries(failedLogins)) {
      if (count >= threshold) {
        return {
          threatDetected: true,
          details: {
            sourceIP: ip,
            failedAttempts: count,
            windowMinutes: 5,
            sampleEvents: context.logs.filter((e) => e.sourceIP === ip && e.eventID === 4625).slice(0, 5),
          },
        };
      }
    }

    return { threatDetected: false, details: null };
  }

  protected async respond(
    context: PlaybookContext,
    details: any
  ): Promise<Array<ActionResult>> {
    const actions: Array<ActionResult> = [];
    const { sourceIP } = details;

    // Example actions – replace with your actual orchestration (e.g., call firewall API, run script, etc.)
    // 1️⃣ Block source IP at the perimeter firewall
    try {
      // await firewallApi.blockIP(sourceIP);
      actions.push({
        action: 'block_ip',
        target: sourceIP,
        status: 'success',
        timestamp: new Date().toISOString(),
        details: { note: 'Firewall block simulated' },
      });
    } catch (err) {
      actions.push({
        action: 'block_ip',
        target: sourceIP,
        status: 'failed',
        timestamp: new Date().toISOString(),
        error: err instanceof Error ? err.message : String(err),
      });
    }

    // 2️⃣ Notify SOC via Telegram (using the HSEC Agent messaging tool)
    try {
      // await sendMessage({ target: 'telegram', message: `🚨 RDP brute force detected from ${sourceIP}. Blocked.` });
      actions.push({
        action: 'notify_telegram',
        target: `group:${process.env.TELEGRAM_GROUP_ID}`,
        status: 'success',
        timestamp: new Date().toISOString(),
        details: { message: `RDP brute force detected from ${sourceIP}.` },
      });
    } catch (err) {
      actions.push({
        action: 'notify_telegram',
        status: 'failed',
        timestamp: new Date().toISOString(),
        error: err instanceof Error ? err.message : String(err),
      });
    }

    // 3️⃣ Create a ticket in your ITSM (optional)
    // ...

    return actions;
  }

  protected async enrich(
    context: PlaybookContext,
    details: any
  ): Promise<Array<EnrichmentResult>> {
    const enrichments: Array<EnrichmentResult> = [];
    const { sourceIP } = details;

    // Example: query AbuseCH, OTX, or internal TI feed
    // In practice, you would call external APIs or lookup in a local TI store.
    try {
      // const abuseCh = await otxAPI.getIPReputation(sourceIP);
      enrichments.push({
        feed: 'OTX (simulated)',
        indicator: sourceIP,
        reputation: 'malicious',
        tags: ['brute-force', 'rdp'],
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      // enrichment failures should not block the playbook
      enrichments.push({
        feed: 'OTX (simulated)',
        indicator: sourceIP,
        status: 'error',
        error: err instanceof Error ? err.message : String(err),
        timestamp: new Date().toISOString(),
      });
    }

    // Add geo‑location enrichment (optional)
    // ...

    return enrichments;
  }
}

/* ------------------------------------------------------------------ */
/* TypeScript interfaces – adjust to match your actual types.ts file   */
/* ------------------------------------------------------------------ */

export interface PlaybookContext {
  /** Raw log entries or alert objects coming from the ingestion pipeline */
  logs: LogEntry[];
  /** Any pre‑processed data (e.g., aggregated counts) */
  aggregated?: Record<string, any>;
  /** Additional metadata (timestamp, source, etc.) */
  metadata?: Record<string, any>;
}

export interface LogEntry {
  eventID: number;
  logonType?: number;
  sourceIP: string;
  timestamp: number; // epoch ms
  [key: string]: any;
}

export interface DetectionResult {
  threatDetected: boolean;
  details: any | null;
}

export interface ActionResult {
  action: string; // e.g., 'block_ip', 'notify_telegram'
  target?: string;
  status: 'success' | 'failed';
  timestamp: string; // ISO string
  details?: Record<string, any>;
  error?: string;
}

export interface EnrichmentResult {
  feed: string; // name of the TI feed (OTX, AbuseCH, internal)
  indicator: string; // e.g., IP, URL, hash
  reputation?: string; // malicious, benign, suspicious
  tags?: string[];
  timestamp: string;
  status?: 'success' | 'error';
  error?: string;
}

export interface PlaybookResult {
  playbookId: string;
  threatDetected: boolean;
  actions: Array<ActionResult>;
  enrichment: Array<EnrichmentResult>;
}

/* ------------------------------------------------------------------ */
/* Example usage (for illustration only)                               */
/* ------------------------------------------------------------------ */
// async function runExample() {
//   const context: PlaybookContext = {
//     logs: [ /* fill with your log data */ ],
//   };
//   const playbook = new RdpBruteForcePlaybook();
//   const result = await playbook.execute(context);
//   console.log(JSON.stringify(result, null, 2));
// }
// runExample();
