// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { AddDiskModal, AddNicModal } from './VmwareResourceModals'

/**
 * Audit line 1383: these modals had zero accessible names — every control was
 * reachable but anonymous to a screen reader. The visible <label> inside Field
 * already carries the vSphere wording, so the fix binds it via htmlFor/id.
 * Querying by label text is what proves the association exists: getByLabelText
 * only resolves through htmlFor/id, aria-label or a wrapping <label>.
 */
const vm = { id: 'vm-1', name: 'web01', datastore_id: 'ds-1', disks: [{ scsi_unit: 0 }] }
const datastores = [{ id: 'ds-1', name: 'datastore1', accessible: true }]
const networks = [{ id: 'net-1', name: 'VM Network', vlan_id: 10 }]
const noop = () => {}

describe('VMware resource modals accessibility', () => {
  afterEach(() => cleanup())

  it('gives every Add Disk control an accessible name from its visible label', () => {
    render(<AddDiskModal vm={vm} datastores={datastores} onClose={noop} onAction={noop} />)
    expect(screen.getByLabelText('Size (GB)')).toBeTruthy()
    expect(screen.getByLabelText('Provisioning')).toBeTruthy()
    expect(screen.getByLabelText('Datastore')).toBeTruthy()
    expect(screen.getByLabelText('SCSI node (auto)')).toBeTruthy()
  })

  it('keeps the emulated vSphere wording as the accessible name', () => {
    render(<AddNicModal vm={vm} networks={networks} onClose={noop} onAction={noop} />)
    // Wording must match what the product teaches, not a paraphrase.
    expect(screen.getByLabelText('Port group / network').tagName).toBe('SELECT')
    expect(screen.getByLabelText('Adapter type').tagName).toBe('SELECT')
  })

  it('names the icon-only close button', () => {
    render(<AddDiskModal vm={vm} datastores={datastores} onClose={noop} onAction={noop} />)
    expect(screen.getByRole('button', { name: 'Close dialog' })).toBeTruthy()
  })

  it('exposes a dialog landmark with focusable panel', () => {
    render(<AddDiskModal vm={vm} datastores={datastores} onClose={noop} onAction={noop} />)
    const dialog = screen.getByRole('dialog', { name: /Add Hard Disk/ })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(dialog.hasAttribute('tabindex')).toBe(true)
  })

  it('leaves no form control without an accessible name', () => {
    const { container } = render(
      <AddDiskModal vm={vm} datastores={datastores} onClose={noop} onAction={noop} />,
    )
    // useId() emits ids containing ':', which is not a valid CSS selector, so
    // match the for-attribute by value rather than via querySelector.
    const labelledIds = new Set(
      [...container.querySelectorAll('label[for]')].map(l => l.getAttribute('for')),
    )
    const unnamed = [...container.querySelectorAll('input, select, textarea')].filter(el => {
      if (el.getAttribute('aria-label')) return false
      if (el.closest('label')) return false
      return !(el.id && labelledIds.has(el.id))
    })
    expect(unnamed.map(el => el.outerHTML)).toEqual([])
  })
})
