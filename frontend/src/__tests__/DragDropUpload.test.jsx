import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DragDropUpload from '../components/DragDropUpload'

const mockAddToast = vi.fn()

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({ t: (key) => key, lang: 'en' }),
}))

vi.mock('../components/Toast', () => ({
  useToast: () => ({ addToast: mockAddToast }),
  ToastProvider: ({ children }) => children,
}))

function createFile(name, sizeBytes, type) {
  const buffer = new ArrayBuffer(sizeBytes)
  return new File([buffer], name, { type })
}

describe('DragDropUpload', () => {
  const onFileSelect = vi.fn()
  const onRemove = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the drop zone when no file is selected', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    expect(screen.getByRole('button')).toBeInTheDocument()
    expect(screen.getByText('analyze.upload_desc')).toBeInTheDocument()
    expect(screen.getByText('analyze.browse')).toBeInTheDocument()
  })

  it('renders file preview when a file is provided', () => {
    const file = createFile('resume.pdf', 1024, 'application/pdf')
    render(<DragDropUpload onFileSelect={onFileSelect} file={file} onRemove={onRemove} />)

    expect(screen.getByText('resume.pdf')).toBeInTheDocument()
    expect(screen.getByText('1 KB')).toBeInTheDocument()
  })

  it('calls onFileSelect for a valid PDF file', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const input = document.querySelector('input[type="file"]')
    const file = createFile('resume.pdf', 5000, 'application/pdf')

    fireEvent.change(input, { target: { files: [file] } })

    expect(onFileSelect).toHaveBeenCalledWith(file)
    expect(mockAddToast).not.toHaveBeenCalled()
  })

  it('calls onFileSelect for a valid DOCX file', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const input = document.querySelector('input[type="file"]')
    const file = createFile('resume.docx', 5000, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    fireEvent.change(input, { target: { files: [file] } })

    expect(onFileSelect).toHaveBeenCalledWith(file)
  })

  it('calls onFileSelect for a valid TXT file', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const input = document.querySelector('input[type="file"]')
    const file = createFile('resume.txt', 500, 'text/plain')

    fireEvent.change(input, { target: { files: [file] } })

    expect(onFileSelect).toHaveBeenCalledWith(file)
  })

  it('rejects files larger than 10MB with a toast', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const input = document.querySelector('input[type="file"]')
    const bigFile = createFile('huge.pdf', 11 * 1024 * 1024, 'application/pdf')

    fireEvent.change(input, { target: { files: [bigFile] } })

    expect(onFileSelect).not.toHaveBeenCalled()
    expect(mockAddToast).toHaveBeenCalledWith(
      expect.any(String),
      'error'
    )
  })

  it('rejects unsupported file formats with a toast', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const input = document.querySelector('input[type="file"]')
    const exeFile = createFile('virus.exe', 1000, 'application/x-msdownload')

    fireEvent.change(input, { target: { files: [exeFile] } })

    expect(onFileSelect).not.toHaveBeenCalled()
    expect(mockAddToast).toHaveBeenCalledWith(
      expect.any(String),
      'error'
    )
  })

  it('calls onRemove when the remove button is clicked', async () => {
    const file = createFile('resume.pdf', 1024, 'application/pdf')
    render(<DragDropUpload onFileSelect={onFileSelect} file={file} onRemove={onRemove} />)

    const removeBtn = screen.getByLabelText(/remove/i)
    await userEvent.click(removeBtn)

    expect(onRemove).toHaveBeenCalledTimes(1)
  })

  it('handles drag-and-drop of a valid file', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const dropZone = screen.getByRole('button')
    const file = createFile('resume.pdf', 5000, 'application/pdf')

    fireEvent.dragOver(dropZone)
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    })

    expect(onFileSelect).toHaveBeenCalledWith(file)
  })

  it('activates file input on Enter key when no file is selected', () => {
    render(<DragDropUpload onFileSelect={onFileSelect} file={null} onRemove={onRemove} />)

    const dropZone = screen.getByRole('button')
    const input = document.querySelector('input[type="file"]')
    const clickSpy = vi.spyOn(input, 'click')

    fireEvent.keyDown(dropZone, { key: 'Enter' })

    expect(clickSpy).toHaveBeenCalled()
  })
})
