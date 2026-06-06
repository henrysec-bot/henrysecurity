/**
 * Playbook for detecting data exfiltration via DNS (e.g., large TXT queries, unusual subdomains).
 * This is a simplified sandboxed example – replace detection logic with real DNS logs and enrichment with actual TI feeds.
 */

import { PlaybookContext, PlaybookResult } from './types';

export class DnsExfiltrationPlaybook extends BasePlaybook {
  constructor() {
    super(
      'dns-exfiltration',
      'DNS Exfiltration Detector',
      'Detects unusually large DNS TXT queries or high entropy subdomains indicative of data exfiltration.'
    );
  }

  protected async analyze(context: PlaybookContext): Promise<DetectionResult> {
    // Example: look for DNS queries with type TXT and length > threshold
    const dnsLogs = context.logs.filter((e) => e.eventType === 'dns_query' && e.queryType === 'TXT');
    const threshold = 100; // characters in query name (excluding domain)
    for (const log of dnsLogs) {
      const queryName = log.queryName; // e.g., "AAABBBCCC...example.com"
      // Extract subdomain part (everything before the last two labels if we assume domain.com)
      const parts = queryName.split('.');
      if (parts.length < 3) continue; // need at least sub.domain.tld
      const subdomain = parts.slice(0, -2).join('.');
      if (subdomain.length >= threshold) {
        // Optional: calculate entropy to avoid false positives on long legit subdomains
        const entropy = this.calculateEntropy(subdomain);
        if (entropy > 3.5) { // arbitrary threshold
          return {
            threatDetected: true,
            details: {
              queryName,
              subdomainLength: subdomain.length,
              entropy,
              clientIP: log.clientIP,
              timestamp: log.timestamp,
            },
          };
        }
      }
    }

    return { threatDetected: false, details: null };
  }

  protected async respond(
    context: PlaybookContext,
    details: any
  ): Promise<Array<ActionResult>> {
    const actions: Array<ActionResult> = [];
    const { clientIP, queryName } = details;

    // Block client IP at firewall/resolver
    try {
      // await firewallApi.blockIP(clientIP);
      actions.push({
        action: 'block_ip',
        target: clientIP,
        status: 'success',
        timestamp: new Date().toISOString(),
        details: { note: `Blocked source of DNS exfiltration: ${queryName}` },
      });
    } catch (err) {
      actions.push({
        action: 'block_ip',
        target: clientIP,
        status: 'failed',
        timestamp: new Date().toISOString(),
        error: err instanceof Error ? err.message : String(err),
      });
    }

    // Notify SOC via Telegram
    try {
      // await sendMessage({ target: 'telegram', message: `🚨 DNS exfiltration detected from ${clientIP} (query: ${queryName}). Blocked.` });
      actions.push({
        action: 'notify_telegram',
        target: `group:${process.env.TELEGRAM_GROUP_ID}`,
        status: 'success',
        timestamp: new Date().toISOString(),
        details: { message: `DNS exfiltration detected from ${clientIP}.` },
      });
    } catch (err) {
      actions.push({
        action: 'notify_telegram',
        status: 'failed',
        timestamp: new Date().toISOString(),
        error: err instanceof Error ? err.message : String(err),
      });
    }

    return actions;
  }

  protected async enrich(
    context: PlaybookContext,
    details: any
  ): Promise<Array<EnrichmentResult>> {
    const enrichments: Array<EnrichmentResult> = [];
    const { clientIP } = details;

    // Simulated TI enrichment
    try {
      // const rep = await otxAPI.getIPReputation(clientIP);
      enrichments.push({
        feed: 'OTX (simulated)',
        indicator: clientIP,
        reputation: 'malicious',
        tags: ['dns-exfiltration'],
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      enrichments.push({
        feed: 'OTX (simulated)',
        indicator: clientIP,
        status: 'error',
        error: err instanceof Error ? err.message : String(err),
        timestamp: new Date().toISOString(),
      });
    }

    return enrichments;
  }

  /** Simple Shannon entropy calculator for a string */
  private calculateEntropy(str: string): number {
    const freq: { [ch: string]: number } = {};
    for (const ch of str) {
      freq[ch] = (freq[ch] || 0) + 1;
    }
    let entropy = 0;
    const length = str.length;
    for (const ch in freq) {
      const p = freq[ch] / length;
      if (p > 0) entropy -= p * Math.log2(p);
    }
    return entropy;
  }
}