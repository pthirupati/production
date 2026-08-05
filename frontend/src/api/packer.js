import { baremetalApi } from './baremetal'

/**
 * Packer Image Factory API — CI pipeline state on the baremetal session.
 */
export const packerApi = {
  getFactoryState(sessionId) {
    return baremetalApi.action(sessionId, 'packer_factory_get_state', {})
  },

  markBuild(sessionId, { sku = 'h100', success = true } = {}) {
    return baremetalApi.action(sessionId, 'packer_factory_mark_build', { sku, success })
  },

  startPipeline(sessionId, { sku = 'h100', files = {}, template = '' } = {}) {
    return baremetalApi.action(sessionId, 'packer_factory_start_pipeline', {
      sku,
      files,
      template,
    })
  },

  advanceJob(sessionId, payload = {}) {
    return baremetalApi.action(sessionId, 'packer_factory_advance_job', payload)
  },

  getJobLogs(sessionId, jobId) {
    return baremetalApi.action(sessionId, 'packer_factory_get_job_logs', { job_id: jobId })
  },

  rerunJob(sessionId, jobId, extra = {}) {
    return baremetalApi.action(sessionId, 'packer_factory_rerun_job', {
      job_id: jobId,
      ...extra,
    })
  },

  publishArtifact(sessionId, { sku, boot_resource, source } = {}) {
    return baremetalApi.action(sessionId, 'packer_factory_publish_artifact', {
      sku,
      boot_resource,
      source,
    })
  },
}

export default packerApi
