// @vitest-environment jsdom
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import ADUC from './ADUC'

/**
 * Audit line 1383: ADUC had zero accessible names. Every field already showed
 * the real Active Directory caption in an adjacent <span>, so the labels reuse
 * that exact wording — a learner being taught "User logon name" must hear
 * "User logon name", not a paraphrase.
 */
function openNewUserWizard() {
  render(<ADUC />)
  fireEvent.click(screen.getByRole('button', { name: /New User/i }))
}

describe('ADUC accessibility', () => {
  afterEach(() => cleanup())

  it('names the New User wizard fields with the Active Directory captions', () => {
    openNewUserWizard()
    for (const name of ['First name', 'Last name', 'Full name', 'User logon name']) {
      expect(screen.getByLabelText(name)).toBeTruthy()
    }
  })

  it('keeps each accessible name identical to its visible caption', () => {
    // Open the user properties sheet: it holds the largest block of captioned
    // fields, and they only mount once the dialog is open.
    const { container } = render(<ADUC />)
    // Group rows render first and are not clickable; user rows carry the
    // second column "User".
    const userRow = [...container.querySelectorAll('.winos-main tbody tr')]
      .find(tr => tr.children[1]?.textContent === 'User')
    expect(userRow).toBeTruthy()
    fireEvent.doubleClick(userRow)
    // The properties sheet must actually be open or this test proves nothing.
    expect(screen.getByLabelText('Telephone number')).toBeTruthy()
    // A label that disagrees with the caption on screen is worse than none:
    // the screen reader would teach the wrong AD terminology.
    const mismatches = []
    for (const el of document.body.querySelectorAll('[aria-label]')) {
      const caption = el.previousElementSibling
      if (caption?.tagName === 'SPAN' && caption.textContent.endsWith(':')) {
        const expected = caption.textContent.slice(0, -1).trim()
        if (el.getAttribute('aria-label') !== expected) {
          mismatches.push(`${expected} != ${el.getAttribute('aria-label')}`)
        }
      }
    }
    expect(mismatches).toEqual([])
  })

  it('leaves no unnamed text field in the New User wizard', () => {
    openNewUserWizard()
    const dialog = document.body
    const unnamed = [...dialog.querySelectorAll('input, select, textarea')].filter(el => {
      if (el.type === 'checkbox' || el.type === 'radio') return false
      return !el.getAttribute('aria-label') && !el.closest('label')
    })
    expect(unnamed.map(el => el.outerHTML)).toEqual([])
  })
})
