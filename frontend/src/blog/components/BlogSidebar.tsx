export default function BlogSidebar() {
  return (
    <div className="space-y-6">
      <div className="bg-[#111a2e] p-4 rounded-xl">
        <input placeholder="Ara..." className="w-full bg-[#0b1220] p-2 rounded" />
      </div>
      <div className="bg-[#111a2e] p-4 rounded-xl">
        <h3 className="font-semibold mb-3">Popüler Yazılar</h3>
        <p className="text-gray-400">CV Hazırlama</p>
        <p className="text-gray-400">Yapay zeka</p>
      </div>
    </div>
  );
}
