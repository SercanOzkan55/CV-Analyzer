import React, { useEffect, useState } from "react";
import { ExternalLink, Clock, Heart, MessageCircle, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { fetchBlogFeed } from "../../api";

interface Article {
  id: number;
  title: string;
  summary: string;
  url: string;
  image: string;
  author: string;
  author_avatar: string;
  published_at: string;
  reading_time: number;
  tags: string[];
  reactions: number;
  comments: number;
  source: string;
}

const TAG_COLORS: Record<string, string> = {
  career: "#c084fc",
  webdev: "#3b82f6",
  programming: "#6366f1",
  ai: "#10b981",
  python: "#f59e0b",
  javascript: "#eab308",
  react: "#06b6d4",
  tutorial: "#f97316",
};

export default function TrendingArticles() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBlogFeed()
      .then((data) => { setArticles(data?.articles || []); setLoading(false); })
      .catch(() => { setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="trending-section">
        <div className="trending-header">
          <TrendingUp size={18} />
          <h2>Trending Articles</h2>
          <span className="trending-badge">Dev.to</span>
        </div>
        <div className="trending-loading">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="trending-skeleton" />
          ))}
        </div>
      </div>
    );
  }

  if (!articles.length) return null;

  return (
    <div className="trending-section">
      <div className="trending-header">
        <TrendingUp size={18} style={{ color: "var(--color-accent)" }} />
        <h2>Trending Articles</h2>
        <span className="trending-badge">Dev.to</span>
      </div>
      <div className="trending-grid">
        {articles.map((article, i) => (
          <motion.a
            key={article.id}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="trending-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07, duration: 0.35 }}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
          >
            {article.image && (
              <div className="trending-card-img-wrap">
                <img src={article.image} alt="" className="trending-card-img" loading="lazy" />
              </div>
            )}
            <div className="trending-card-body">
              <h3 className="trending-card-title">{article.title}</h3>
              <p className="trending-card-summary">{article.summary}</p>

              <div className="trending-card-tags">
                {article.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    className="trending-tag"
                    style={{ borderColor: TAG_COLORS[tag] || "var(--color-border)" }}
                  >
                    #{tag}
                  </span>
                ))}
              </div>

              <div className="trending-card-footer">
                <div className="trending-card-author">
                  {article.author_avatar && (
                    <img src={article.author_avatar} alt="" className="trending-author-avatar" />
                  )}
                  <span>{article.author}</span>
                </div>
                <div className="trending-card-stats">
                  <span><Heart size={12} /> {article.reactions}</span>
                  <span><MessageCircle size={12} /> {article.comments}</span>
                  <span><Clock size={12} /> {article.reading_time} dk</span>
                </div>
              </div>
            </div>
            <ExternalLink size={14} className="trending-external-icon" />
          </motion.a>
        ))}
      </div>
    </div>
  );
}
