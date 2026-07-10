import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { labApi } from '../api/labs'
import { useLabStore } from '../store/labStore'
import { broadcastLabStopped, closeLabChildTabs } from '../utils/labSync'

const PROVISIONING_TIMEOUT = { docker: 120, cloud: 300 }

/**
 * Poll lab session status while PROVISIONING and bootstrap RUNNING sessions.
 */
export function useLabProvisioning(sessionId, { onRunning, onHints }) {
  const navigate = useNavigate()
  const stopTimer = useLabStore((s) => s.stopTimer)
  const clearSession = useLabStore((s) => s.clearSession)

  const [loading, setLoading] = useState(true)
  const [provisioning, setProvisioning] = useState(false)
  const [provisioningStep, setProvisioningStep] = useState(0)
  const [provisioningElapsed, setProvisioningElapsed] = useState(0)
  const [provisioningStuck, setProvisioningStuck] = useState(false)
  const [isCloudLab, setIsCloudLab] = useState(false)
  const [provisionError, setProvisionError] = useState(null)

  useEffect(() => {
    let pollTimer = null
    let cancelled = false
    let elapsedCounter = 0
    let networkErrors = 0

    const loadSession = async () => {
      try {
        const lab = await labApi.getSessionStatus(sessionId)
        if (cancelled) return
        networkErrors = 0
        setProvisionError(null)

        if (!lab) {
          toast.error('Lab session not found')
          navigate('/scenarios')
          return
        }

        if (lab.status === 'PROVISIONING') {
          setProvisioning(true)
          const cloud = lab.provider === 'aws_ec2' || lab.provider === 'digitalocean'
          setIsCloudLab(cloud)
          elapsedCounter += 3
          setProvisioningElapsed(elapsedCounter)
          const timeoutSec = cloud ? PROVISIONING_TIMEOUT.cloud : PROVISIONING_TIMEOUT.docker
          if (elapsedCounter >= timeoutSec) setProvisioningStuck(true)
          if (cloud) {
            setProvisioningStep((prev) => {
              if (prev === 0) return 1
              if (prev === 1 && elapsedCounter > 15) return 2
              if (prev === 2 && elapsedCounter > 40) return 3
              if (prev === 3 && elapsedCounter > 70) return 4
              return prev
            })
          } else {
            setProvisioningStep((prev) => Math.min(prev + 1, 3))
          }
          pollTimer = setTimeout(loadSession, 3000)
          return
        }

        if (lab.status === 'RUNNING') {
          setProvisioning(false)
          setProvisioningStuck(false)
          onRunning?.(lab)
          setLoading(false)
          return
        }

        if (lab.status === 'FAILED') {
          setProvisioning(false)
          setLoading(false)
          const msg = lab.error_message || lab.provision_error || 'Server failed to launch. Please try again.'
          setProvisionError(msg)
          toast.error(msg)
          navigate(`/scenarios/${lab.scenario?.slug || ''}`)
          return
        }

        toast.error(`Lab session ended (${lab.status.toLowerCase()})`)
        navigate('/scenarios')
      } catch (err) {
        if (cancelled) return
        if (err.response?.status === 404) {
          toast.error('Lab session not found')
          navigate('/scenarios')
          return
        }
        networkErrors += 1
        if (networkErrors >= 3) {
          setProvisionError('Connection lost while loading the lab. Retrying…')
          toast.error('Connection issue — retrying lab status…', { id: 'lab-provision-net' })
        }
        pollTimer = setTimeout(loadSession, 5000)
      }
    }

    loadSession()
    labApi.getHints(sessionId).then((data) => onHints?.(data)).catch(() => {})

    return () => {
      cancelled = true
      if (pollTimer) clearTimeout(pollTimer)
      stopTimer()
    }
  }, [sessionId, navigate, onRunning, onHints, stopTimer, clearSession])

  return {
    loading,
    provisioning,
    provisioningStep,
    provisioningElapsed,
    provisioningStuck,
    isCloudLab,
    provisionError,
    setProvisioningStuck,
    setProvisioningElapsed,
  }
}
