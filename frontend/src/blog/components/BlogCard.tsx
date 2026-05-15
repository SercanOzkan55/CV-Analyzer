import { useNavigate } from "react-router-dom";

type BlogPost = {
  slug: string;
  image: string;
  category: string;
  title: string;
  summary: string;
};

export default function BlogCard({ post }: { post: BlogPost }) {
  const navigate = useNavigate();
  return (
    <div
      onClick={() => navigate(`/blog/${post.slug}`)}
      className="bg-[#111a2e] rounded-xl overflow-hidden cursor-pointer hover:opacity-90"
    >
      <img src={post.image} className="w-full h-48 object-cover" />
      <div className="p-5">
        <span className="text-cyan-400 text-sm">{post.category}</span>
        <h2 className="text-xl font-semibold mt-2">{post.title}</h2>
        <p className="text-gray-400 mt-2">{post.summary}</p>
      </div>
    </div>
  );
}
