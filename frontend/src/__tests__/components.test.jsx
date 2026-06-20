// Frontend Component Tests - React + Vitest
// Test file: frontend/src/__tests__/components.test.jsx

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter as Router } from 'react-router-dom';

// Import components to test
import AuthForm from '../components/AuthForm';
import Dashboard from '../pages/Dashboard';
import CVAnalyzer from '../components/CVAnalyzer';
import RecruiterDashboard from '../pages/RecruiterPage';
import Toast from '../components/Toast';

// Mock API calls
vi.mock('../api.js', () => ({
  loginUser: vi.fn(),
  signupUser: vi.fn(),
  analyzeCV: vi.fn(),
  uploadFile: vi.fn(),
}));

describe('AuthForm Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form', () => {
    render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  it('validates email format', async () => {
    const user = userEvent.setup();
    render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, 'invalid-email');
    
    const submitButton = screen.getByRole('button', { name: /login/i });
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('submits form with valid data', async () => {
    const user = userEvent.setup();
    const { loginUser } = await import('../api.js');
    loginUser.mockResolvedValue({ id: '123', email: 'test@example.com' });
    
    render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'SecurePass123!');
    
    await user.click(screen.getByRole('button', { name: /login/i }));
    
    await waitFor(() => {
      expect(loginUser).toHaveBeenCalledWith('test@example.com', 'SecurePass123!');
    });
  });

  it('shows error on failed login', async () => {
    const user = userEvent.setup();
    const { loginUser } = await import('../api.js');
    loginUser.mockRejectedValue(new Error('Invalid credentials'));
    
    render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrongpass');
    await user.click(screen.getByRole('button', { name: /login/i }));
    
    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });

  it('toggles between login and signup modes', async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
    
    rerender(
      <Router>
        <AuthForm mode="signup" />
      </Router>
    );
    
    expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument();
  });
});

describe('CVAnalyzer Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders file upload input', () => {
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    expect(screen.getByText(/upload cv/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('handles file upload', async () => {
    const user = userEvent.setup();
    const { uploadFile } = await import('../api.js');
    uploadFile.mockResolvedValue({ task_id: 'task-123' });
    
    const file = new File(['cv content'], 'resume.pdf', { type: 'application/pdf' });
    
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    const input = screen.getByRole('button');
    // Simulate file drop or input
    fireEvent.drop(input, {
      dataTransfer: {
        files: [file],
      },
    });
    
    await waitFor(() => {
      expect(uploadFile).toHaveBeenCalledWith(expect.any(FormData));
    });
  });

  it('displays loading state during analysis', async () => {
    const { uploadFile, analyzeCV } = await import('../api.js');
    
    uploadFile.mockResolvedValue({ task_id: 'task-123' });
    // Simulate delay
    analyzeCV.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 1000)));
    
    const user = userEvent.setup();
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    // Upload file
    const file = new File(['content'], 'resume.pdf', { type: 'application/pdf' });
    fireEvent.drop(screen.getByRole('button'), {
      dataTransfer: { files: [file] },
    });
    
    await waitFor(() => {
      expect(screen.getByText(/analyzing/i) || screen.getByText(/in progress/i)).toBeInTheDocument();
    });
  });

  it('displays analysis results', async () => {
    const { uploadFile, analyzeCV } = await import('../api.js');
    
    uploadFile.mockResolvedValue({ task_id: 'task-123' });
    analyzeCV.mockResolvedValue({
      ats_score: 85,
      match_score: 92,
      skills: ['JavaScript', 'React', 'Python'],
      recommendations: ['Add more backend experience'],
    });
    
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    // Simulate upload and wait for results
    const file = new File(['content'], 'resume.pdf', { type: 'application/pdf' });
    fireEvent.drop(screen.getByRole('button'), {
      dataTransfer: { files: [file] },
    });
    
    await waitFor(() => {
      expect(screen.getByText(/85/)).toBeInTheDocument(); // ATS score
      expect(screen.getByText(/92/)).toBeInTheDocument(); // Match score
    });
  });

  it('prevents invalid file types', async () => {
    const user = userEvent.setup();
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    // Try uploading invalid file
    const file = new File(['content'], 'image.png', { type: 'image/png' });
    fireEvent.drop(screen.getByRole('button'), {
      dataTransfer: { files: [file] },
    });
    
    await waitFor(() => {
      expect(screen.getByText(/invalid file type|pdf, docx, txt/i)).toBeInTheDocument();
    });
  });
});

describe('Dashboard Component', () => {
  it('renders user dashboard', () => {
    render(
      <Router>
        <Dashboard user={{ name: 'John', email: 'john@example.com' }} />
      </Router>
    );
    
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/john/i)).toBeInTheDocument();
  });

  it('displays analysis history', () => {
    const analyses = [
      { id: 1, filename: 'resume1.pdf', ats_score: 85, date: '2024-01-01' },
      { id: 2, filename: 'resume2.pdf', ats_score: 92, date: '2024-01-02' },
    ];
    
    render(
      <Router>
        <Dashboard user={{ name: 'John' }} analyses={analyses} />
      </Router>
    );
    
    expect(screen.getByText(/resume1.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/resume2.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/85/)).toBeInTheDocument();
    expect(screen.getByText(/92/)).toBeInTheDocument();
  });

  it('allows deleting analysis', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    
    render(
      <Router>
        <Dashboard 
          user={{ name: 'John' }} 
          analyses={[{ id: 1, filename: 'resume.pdf' }]}
          onDelete={onDelete}
        />
      </Router>
    );
    
    const deleteButton = screen.getByRole('button', { name: /delete/i });
    await user.click(deleteButton);
    
    expect(onDelete).toHaveBeenCalledWith(1);
  });
});

describe('RecruiterDashboard Component', () => {
  it('renders recruiter dashboard', () => {
    render(
      <Router>
        <RecruiterDashboard user={{ role: 'recruiter' }} />
      </Router>
    );
    
    expect(screen.getByText(/recruiter/i) || screen.getByText(/jobs/i)).toBeInTheDocument();
  });

  it('allows creating new job posting', async () => {
    const user = userEvent.setup();
    const onCreateJob = vi.fn();
    
    render(
      <Router>
        <RecruiterDashboard user={{ role: 'recruiter' }} onCreateJob={onCreateJob} />
      </Router>
    );
    
    const createButton = screen.getByRole('button', { name: /create job/i });
    await user.click(createButton);
    
    // Fill form
    await user.type(screen.getByLabelText(/job title/i), 'Senior Developer');
    await user.type(screen.getByLabelText(/description/i), 'We need an experienced dev...');
    
    await user.click(screen.getByRole('button', { name: /create|submit/i }));
    
    await waitFor(() => {
      expect(onCreateJob).toHaveBeenCalledWith(expect.objectContaining({
        title: 'Senior Developer',
      }));
    });
  });

  it('displays job candidates for ranking', () => {
    const candidates = [
      { id: 1, name: 'Alice', match_score: 95 },
      { id: 2, name: 'Bob', match_score: 82 },
    ];
    
    render(
      <Router>
        <RecruiterDashboard 
          user={{ role: 'recruiter' }} 
          candidates={candidates}
          jobId={1}
        />
      </Router>
    );
    
    expect(screen.getByText(/alice/i)).toBeInTheDocument();
    expect(screen.getByText(/bob/i)).toBeInTheDocument();
    expect(screen.getByText(/95/)).toBeInTheDocument();
  });
});

describe('Toast Component', () => {
  it('renders success toast', () => {
    render(
      <Toast message="File uploaded successfully" type="success" />
    );
    
    expect(screen.getByText(/uploaded successfully/i)).toBeInTheDocument();
  });

  it('renders error toast', () => {
    render(
      <Toast message="Upload failed" type="error" />
    );
    
    expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
  });

  it('auto-dismisses after timeout', async () => {
    const { unmount } = render(
      <Toast message="Test message" type="info" autoClose={true} delay={100} />
    );
    
    expect(screen.getByText(/test message/i)).toBeInTheDocument();
    
    // Wait for auto-dismiss
    await waitFor(() => {
      expect(screen.queryByText(/test message/i)).not.toBeInTheDocument();
    }, { timeout: 200 });
  });

  it('allows manual close', async () => {
    const user = userEvent.setup();
    render(
      <Toast message="Test message" type="info" closeable={true} />
    );
    
    const closeButton = screen.getByRole('button', { name: /close|×/i });
    await user.click(closeButton);
    
    expect(screen.queryByText(/test message/i)).not.toBeInTheDocument();
  });
});

describe('Accessibility Tests', () => {
  it('all form inputs have labels', () => {
    render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    const inputs = screen.getAllByRole('textbox');
    inputs.forEach(input => {
      // Check for associated label or aria-label
      const label = document.querySelector(`label[for="${input.id}"]`);
      const hasAriaLabel = input.getAttribute('aria-label');
      
      expect(label || hasAriaLabel).toBeTruthy();
    });
  });

  it('buttons have descriptive text', () => {
    render(
      <Router>
        <Dashboard user={{ name: 'John' }} />
      </Router>
    );
    
    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      expect(button.textContent || button.getAttribute('aria-label')).toBeTruthy();
    });
  });

  it('supports keyboard navigation', async () => {
    const user = userEvent.setup();
    render(
      <Router>
        <AuthForm mode="login" />
      </Router>
    );
    
    // Tab to email input
    await user.tab();
    expect(screen.getByLabelText(/email/i)).toHaveFocus();
    
    // Tab to password
    await user.tab();
    expect(screen.getByLabelText(/password/i)).toHaveFocus();
    
    // Tab to submit button
    await user.tab();
    expect(screen.getByRole('button', { name: /login/i })).toHaveFocus();
  });
});

describe('Security Tests', () => {
  it('sanitizes XSS in user input', async () => {
    const user = userEvent.setup();
    const { uploadFile } = await import('../api.js');
    
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    // Try uploading file with XSS payload in name
    const file = new File(['content'], '<script>alert("xss")</script>.pdf', { type: 'application/pdf' });
    fireEvent.drop(screen.getByRole('button'), {
      dataTransfer: { files: [file] },
    });
    
    // Should escape filename in display
    await waitFor(() => {
      const pageContent = screen.getByText(/script/).textContent;
      expect(pageContent).not.toContain('<script>');
    });
  });

  it('does not expose sensitive data in localStorage', () => {
    // Ensure auth token is not stored in plain localStorage
    const storage = localStorage.getItem('token');
    expect(storage).not.toMatch(/^[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_.+/=]*$/); // JWT pattern
  });

  it('validates file size before upload', async () => {
    const user = userEvent.setup();
    
    render(
      <Router>
        <CVAnalyzer />
      </Router>
    );
    
    // Create file larger than limit (e.g., 100MB)
    const largeFile = new File([new ArrayBuffer(100 * 1024 * 1024)], 'huge.pdf', { type: 'application/pdf' });
    
    fireEvent.drop(screen.getByRole('button'), {
      dataTransfer: { files: [largeFile] },
    });
    
    await waitFor(() => {
      expect(screen.getByText(/file too large|exceeds maximum size/i)).toBeInTheDocument();
    });
  });
});
