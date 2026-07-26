export interface Author {
  name: string;
  email?: string;
  role: string;
  plan: string;
}

export interface Reply {
  id: string;
  author: Author;
  text: string;
  createdAt: string;
  likes: string[];
}

export interface Comment {
  id: string;
  author: Author;
  text: string;
  createdAt: string;
  likes: string[];
  replies: Reply[];
}

export interface BlogPost {
  id: string;
  title: string;
  content: string;
  summary: string;
  category: string;
  slug: string;
  image: string;
  author: Author;
  tags: string[];
  createdAt: string;
  views: number;
  likes: string[];
  comments: Comment[];
}

export function getDailyLimit(plan: string, role: string): number {
  if (role === 'admin') return 999;
  if (role === 'recruiter' || plan === 'pro' || plan === 'enterprise' || plan === 'premium') return 10;
  return 3;
}

const DEFAULT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatDate(dateStr: string, months?: string[]): string {
  const d = new Date(dateStr);
  const m = months && months.length === 12 ? months : DEFAULT_MONTHS;
  return `${d.getDate()} ${m[d.getMonth()]} ${d.getFullYear()}`;
}

export function readingTime(text: string, suffix?: string): string {
  const words = text.split(/\s+/).length;
  const minutes = Math.max(1, Math.ceil(words / 200));
  return suffix?.includes('{min}')
    ? suffix.replace('{min}', String(minutes))
    : `${minutes} ${suffix ?? 'min read'}`;
}

export const CATEGORY_COLORS: Record<string, string> = {
  Technology: 'bg-blue-600',
  'Artificial Intelligence': 'bg-emerald-600',
  Design: 'bg-purple-600',
  'Data Science': 'bg-orange-500',
  Security: 'bg-red-600',
  Cloud: 'bg-sky-500',
  Career: 'bg-cyan-600',
};

export const AVATAR_COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

export function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export function getInitials(name: string): string {
  return name.split(' ').map(word => word[0]).join('').toUpperCase().slice(0, 2);
}
