import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import Modal from '../components/Modal'
import ScoreCircle from '../components/ScoreCircle'

describe('shared UI components', () => {
  it('renders an open modal and calls onClose from the close button', () => {
    const onClose = vi.fn()

    render(
      <Modal open={true} onClose={onClose} title="Confirm action">
        <p>Modal body</p>
      </Modal>
    )

    expect(screen.getByRole('dialog', { name: /confirm action/i })).toBeInTheDocument()
    expect(screen.getByText('Modal body')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /close modal/i }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not render modal content when closed', () => {
    render(
      <Modal open={false} onClose={() => {}} title="Hidden modal">
        <p>Hidden body</p>
      </Modal>
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText('Hidden body')).not.toBeInTheDocument()
  })

  it('renders score circle text with a clamped score', () => {
    render(<ScoreCircle score={124} size={120} label="ATS" />)

    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('ATS')).toBeInTheDocument()
    expect(screen.getByLabelText('ATS: 100%')).toBeInTheDocument()
  })
})
