import api from './client'

/**
 * Cross-technology bridge notifications for the AWS console simulator.
 *
 * Some AWS console mutations have side effects outside the AWS engine itself:
 * attaching an EBS volume should surface as a new block device in a Linux lab
 * terminal sharing the same session, and starting/stopping/rebooting an EC2
 * instance should reflect in that terminal's simulated power state. The
 * backend already understands these two intents as the `bridge_attach_volume`
 * and `bridge_power` action variants on the AWS session endpoint (see
 * apps/vmware_sim/views.py AwsSimActionView) — this helper is a thin,
 * fire-and-forget wrapper so awsStore can call it right alongside its normal
 * optimistic local state update, without ever blocking or rejecting the UI.
 */
export function notifyAwsBridge(sessionId, action, payload = {}) {
  if (!sessionId || !action) return Promise.resolve(null)
  return api
    .post(`/vmware/aws/sessions/${sessionId}/action/`, { action, payload }, { silentError: true })
    .then((r) => r.data)
    .catch(() => null)
}

export default notifyAwsBridge
