import CommentBox from "./components/CommentBox";
import CommentList from "./components/CommentList";
import BlogSidebar from "./components/BlogSidebar";

export default function BlogDetailPage() {
  return (
    <div className="min-h-screen bg-[#0b1220] text-white">
      <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <h1 className="text-3xl font-bold">Yazılım geliştirmede en iyi pratikler</h1>
          <p className="text-gray-400 mt-4">Blog içeriği burada olacak</p>
          <div className="mt-8">
            <CommentBox />
            <CommentList />
          </div>
        </div>
        <BlogSidebar />
      </div>
    </div>
  );
}
