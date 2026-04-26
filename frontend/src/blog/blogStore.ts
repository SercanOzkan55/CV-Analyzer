const STORAGE_KEY = 'cv_analyzer_blog';
const POST_COUNT_KEY = 'cv_analyzer_blog_post_count';

export interface Author {
  name: string;
  email: string;
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

function getSeedPosts(): BlogPost[] {
  return [
    {
      id: 'seed-1',
      title: 'Yazılım Geliştirmede En İyi Pratikler ve Kodlama Standartları',
      content: `Modern yazılım geliştirme süreçlerinde clean code prensipleri, test odaklı geliştirme ve kod kalitesi standartları hakkında bilmeniz gereken her şey.\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.\n\nDuis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.\n\n## Önemli Noktalar\n\nSed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo.`,
      summary: 'Modern yazılım geliştirme süreçlerinde clean code prensipleri, test odaklı geliştirme ve kod kalitesi standartları hakkında bilmeniz gereken her şey.',
      category: 'Teknoloji',
      slug: 'yazilim-gelistirmede-en-iyi-pratikler',
      image: 'https://picsum.photos/id/0/900/400',
      author: { name: 'Ahmet Yılmaz', email: 'ahmet@example.com', role: 'recruiter', plan: 'premium' },
      tags: ['Yazılım', 'Clean Code', 'Teknoloji'],
      createdAt: '2026-03-01T10:00:00Z',
      views: 1247,
      likes: ['user1@ex.com', 'user2@ex.com'],
      comments: [
        {
          id: 'c1',
          author: { name: 'Mehmet Yılmaz', email: 'mehmet@ex.com', role: 'user', plan: 'free' },
          text: 'Harika bir yazı olmuş! Özellikle clean code prensipleriyle ilgili uygulamaları dikkat etmeniz gereken noktaları çok güzel açıklamışsınız. Teşekkürler!',
          createdAt: '2026-03-02T14:00:00Z',
          likes: [],
          replies: [
            {
              id: 'r1',
              author: { name: 'Ahmet Yılmaz', email: 'ahmet@example.com', role: 'recruiter', plan: 'premium' },
              text: 'Teşekkür ederim! İlerleyen yazılarımda daha detaylı kod örnekleri de paylaşacağım.',
              createdAt: '2026-03-02T15:00:00Z',
              likes: []
            }
          ]
        },
        {
          id: 'c2',
          author: { name: 'Ayşe Demir', email: 'ayse@ex.com', role: 'user', plan: 'premium' },
          text: 'Test odaklı geliştirme konusunda daha fazla içerik paylaşır mısınız? Bu konu hakkında öğrenmek istediğim çok şey var.',
          createdAt: '2026-03-03T09:00:00Z',
          likes: [],
          replies: []
        },
        {
          id: 'c3',
          author: { name: 'Can Öztürk', email: 'can@ex.com', role: 'user', plan: 'free' },
          text: 'Kod kalitesi standartları her projede uygulanmalı. Özellikle takım çalışmasında bu çok kritik.',
          createdAt: '2026-03-04T11:00:00Z',
          likes: [],
          replies: []
        },
        {
          id: 'c4',
          author: { name: 'Zeynep Kara', email: 'zeynep@ex.com', role: 'user', plan: 'free' },
          text: 'Bu tarz içeriklere çok ihtiyacımız var. Devamını bekliyoruz!',
          createdAt: '2026-03-05T16:00:00Z',
          likes: ['ahmet@example.com'],
          replies: []
        }
      ]
    },
    {
      id: 'seed-2',
      title: 'Yapay Zeka ve Makine Öğrenmesi: Geleceğin Teknolojileri',
      content: 'Yapay zeka algoritmalarının iş dünyasında kullanımı, makine öğrenmesi modelleri ve AI tabanlı çözümler ile verimliliği artırmanın yolları.\n\nDeep learning, NLP ve computer vision gibi alanlarda son gelişmeler iş süreçlerini köklü bir şekilde değiştirmektedir. Bu yazıda, yapay zeka teknolojilerinin günümüzdeki uygulamalarını ve gelecekte bizi nelerin beklediğini keşfedeceğiz.',
      summary: 'Yapay zeka algoritmalarının iş dünyasında kullanımı, makine öğrenmesi modelleri ve AI tabanlı çözümler ile verimliliği artırmanın yolları.',
      category: 'Yapay Zeka',
      slug: 'yapay-zeka-ve-makine-ogrenmesi',
      image: 'https://picsum.photos/id/60/900/400',
      author: { name: 'Tuğçe Kaya', email: 'tugce@example.com', role: 'user', plan: 'premium' },
      tags: ['Yapay Zeka', 'ML', 'AI'],
      createdAt: '2026-03-05T08:00:00Z',
      views: 892,
      likes: ['user1@ex.com'],
      comments: []
    },
    {
      id: 'seed-3',
      title: 'Web Tasarımında UX/UI Prensipleri ve Kullanıcı Deneyimi',
      content: 'Kullanıcı odaklı tasarım yaklaşımları, responsive tasarım prensipleri ve modern web arayüzleri oluşturmanın püf noktaları.\n\nİyi bir kullanıcı deneyimi, doğru renk paleti ve tipografi seçiminden, akıcı animasyonlara kadar pek çok detayı kapsar. Bu yazıda, modern web tasarımının temel prensiplerini inceliyoruz.',
      summary: 'Kullanıcı odaklı tasarım yaklaşımları, responsive tasarım prensipleri ve modern web arayüzleri oluşturmanın püf noktaları.',
      category: 'Tasarım',
      slug: 'web-tasariminda-ux-ui-prensipleri',
      image: 'https://picsum.photos/id/201/900/400',
      author: { name: 'Mehmet Demir', email: 'mdemir@example.com', role: 'user', plan: 'free' },
      tags: ['UX', 'UI', 'Tasarım'],
      createdAt: '2026-03-07T12:00:00Z',
      views: 654,
      likes: [],
      comments: []
    },
    {
      id: 'seed-4',
      title: 'Veri Bilimi ve Analitik: Veriden Değer Yaratma Stratejileri',
      content: 'Big data analizi, veri görselleştirme ve iş zekası araçlarıyla veriye dayalı karar alma süreçlerini güçlendirmenin yolları.\n\nVeri bilimi, günümüzün en stratejik alanlarından biri haline geldi. İşletmeler, büyük veri setlerini analiz ederek önemli iç görüler elde ediyor ve rekabet avantajı sağlıyor.',
      summary: 'Big data analizi, veri görselleştirme ve iş zekası araçlarıyla veriye dayalı karar alma süreçlerini güçlendirmenin yolları.',
      category: 'Veri Bilimi',
      slug: 'veri-bilimi-ve-analitik',
      image: 'https://picsum.photos/id/180/900/400',
      author: { name: 'Ayşe Öztürk', email: 'aozturk@example.com', role: 'user', plan: 'premium' },
      tags: ['Veri Bilimi', 'Analitik', 'Big Data'],
      createdAt: '2026-03-08T14:00:00Z',
      views: 423,
      likes: ['user3@ex.com'],
      comments: []
    },
    {
      id: 'seed-5',
      title: 'Siber Güvenlik: Dijital Dünyada Güvende Kalmanın Yolları',
      content: 'Siber tehditlere karşı korunma yöntemleri, güvenlik altyapısının önemi ve modern güvenlik protokolleri hakkında bilinmesi gerekenler.\n\nSiber saldırılar her geçen gün artmakta ve hem bireysel hem de kurumsal düzeyde ciddi tehditler oluşturmaktadır. Bu yazıda, güncel siber güvenlik uygulamalarını ve koruma stratejilerini ele alıyoruz.',
      summary: 'Siber tehditlere karşı korunma yöntemleri, güvenlik altyapısının önemi ve modern güvenlik protokolleri hakkında bilinmesi gerekenler.',
      category: 'Güvenlik',
      slug: 'siber-guvenlik-dijital-dunyada',
      image: 'https://picsum.photos/id/366/900/400',
      author: { name: 'Can Akdağ', email: 'can.akdag@example.com', role: 'recruiter', plan: 'premium' },
      tags: ['Güvenlik', 'Siber', 'Teknoloji'],
      createdAt: '2026-03-09T09:00:00Z',
      views: 312,
      likes: [],
      comments: []
    }
  ];
}

export function loadPosts(): BlogPost[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  const seed = getSeedPosts();
  savePosts(seed);
  return seed;
}

export function savePosts(posts: BlogPost[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(posts));
}

interface DailyCount {
  date: string;
  counts: Record<string, number>;
}

function getTodayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function loadDailyCount(): DailyCount {
  try {
    const raw = localStorage.getItem(POST_COUNT_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed.date === getTodayStr()) return parsed;
    }
  } catch { /* ignore */ }
  return { date: getTodayStr(), counts: {} };
}

function saveDailyCount(dc: DailyCount) {
  localStorage.setItem(POST_COUNT_KEY, JSON.stringify(dc));
}

export function getUserPostCountToday(email: string): number {
  const dc = loadDailyCount();
  return dc.counts[email] || 0;
}

export function getDailyLimit(plan: string, role: string): number {
  if (role === 'admin') return 999;
  if (role === 'recruiter' || plan === 'premium') return 10;
  return 3;
}

export function canUserPost(email: string, plan: string, role: string): boolean {
  return getUserPostCountToday(email) < getDailyLimit(plan, role);
}

export function incrementPostCount(email: string) {
  const dc = loadDailyCount();
  dc.counts[email] = (dc.counts[email] || 0) + 1;
  saveDailyCount(dc);
}

export function toSlug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[çÇ]/g, 'c')
    .replace(/[ğĞ]/g, 'g')
    .replace(/[ıİ]/g, 'i')
    .replace(/[öÖ]/g, 'o')
    .replace(/[şŞ]/g, 's')
    .replace(/[üÜ]/g, 'u')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

const DEFAULT_MONTHS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];

export function formatDate(dateStr: string, months?: string[]): string {
  const d = new Date(dateStr);
  const m = months && months.length === 12 ? months : DEFAULT_MONTHS;
  return `${d.getDate()} ${m[d.getMonth()]} ${d.getFullYear()}`;
}

export function readingTime(text: string, suffix?: string): string {
  const words = text.split(/\s+/).length;
  const minutes = Math.max(1, Math.ceil(words / 200));
  return `${minutes} ${suffix ?? 'dk okuma'}`;
}

export const CATEGORY_COLORS: Record<string, string> = {
  'Teknoloji': 'bg-blue-600',
  'Yapay Zeka': 'bg-emerald-600',
  'Tasarım': 'bg-purple-600',
  'Veri Bilimi': 'bg-orange-500',
  'Güvenlik': 'bg-red-600',
  'Cloud': 'bg-sky-500',
  'Kariyer': 'bg-cyan-600',
};

export const AVATAR_COLORS = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

export function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}
