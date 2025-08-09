import crypto from 'crypto'

async function readRawBody(req: any): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = ''
    req.setEncoding('utf8')
    req.on('data', (chunk) => (data += chunk))
    req.on('end', () => resolve(data))
    req.on('error', reject)
  })
}

function verifySlackSignature(signingSecret: string, rawBody: string, timestamp: string, signature: string): boolean {
  if (!timestamp || !signature) return false
  // Reject if timestamp is too old (>5m)
  const ts = parseInt(timestamp, 10)
  if (!Number.isFinite(ts) || Math.abs(Date.now() / 1000 - ts) > 60 * 5) return false

  const base = `v0:${timestamp}:${rawBody}`
  const hash = crypto.createHmac('sha256', signingSecret).update(base).digest('hex')
  const expected = `v0=${hash}`
  // constant-time compare
  try {
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))
  } catch {
    return false
  }
}

function parseForm(body: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const pair of body.split('&')) {
    const [k, v] = pair.split('=')
    if (!k) continue
    out[decodeURIComponent(k)] = decodeURIComponent((v || '').replace(/\+/g, ' '))
  }
  return out
}

async function dispatchToGithub(clientPayload: any): Promise<Response> {
  const repo = process.env.GITHUB_REPOSITORY || 'DJ-RINO/freee-auto-bookkeeping'
  const token = process.env.GITHUB_TOKEN
  if (!token) throw new Error('Missing GITHUB_TOKEN')
  const url = `https://api.github.com/repos/${repo}/dispatches`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'User-Agent': 'vercel-slack-webhook'
    },
    body: JSON.stringify({ event_type: 'apply-receipt-decision', client_payload: clientPayload })
  })
  return res as unknown as Response
}

export default async function handler(req: any, res: any) {
  try {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method Not Allowed' })
      return
    }

    const signingSecret = process.env.SLACK_SIGNING_SECRET
    if (!signingSecret) {
      res.status(500).json({ error: 'Missing SLACK_SIGNING_SECRET' })
      return
    }

    const rawBody = await readRawBody(req)
    const ts = req.headers['x-slack-request-timestamp'] as string
    const sig = req.headers['x-slack-signature'] as string
    if (!verifySlackSignature(signingSecret, rawBody, ts, sig)) {
      res.status(401).json({ error: 'Invalid signature' })
      return
    }

    const ct = (req.headers['content-type'] || '').toString()
    if (!ct.includes('application/x-www-form-urlencoded')) {
      res.status(400).json({ error: 'Unsupported content-type' })
      return
    }

    const form = parseForm(rawBody)
    const payloadStr = form['payload']
    if (!payloadStr) {
      res.status(400).json({ error: 'Missing payload' })
      return
    }

    const payload = JSON.parse(payloadStr)
    // Derive minimal fields for MVP
    const actions = payload.actions || []
    const primary = actions[0] || {}
    let action: 'approve' | 'edit' | 'reject' = 'approve'
    const aid: string = primary.action_id || ''
    if (aid.includes('edit')) action = 'edit'
    if (aid.includes('reject') || aid.includes('skip')) action = 'reject'

    const interaction_id = payload.container?.message_ts || payload.trigger_id || payload.response_url
    const clientPayload = {
      interaction_id,
      action,
      amount: payload.view?.state?.values?.amount || null,
      date: payload.view?.state?.values?.date || null,
      vendor: payload.view?.state?.values?.vendor || null
    }

    const ghRes = await dispatchToGithub(clientPayload)
    if ((ghRes as any).status && (ghRes as any).status !== 204) {
      const text = await (ghRes as any).text?.()
      console.error('dispatch error', (ghRes as any).status, text)
    }

    // Respond quickly to Slack
    res.status(200).json({ ok: true })
  } catch (e: any) {
    console.error(e)
    res.status(500).json({ error: 'internal_error' })
  }
}


