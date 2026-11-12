class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.0.0/mosaik-2.0.0.tar.gz"
  sha256 "3108e525fe2b666027c71ccfed6b04bc13cf20994cadae5075e3e1e5ad0e74af"
  license :cannot_represent

  depends_on "node@24"

  def install
    libexec.install "mosaik.mjs"
    pkgshare.install "guide.md"
    prefix.install "LICENSE"
    (bin/"mosaik").write <<~SH
      #!/bin/sh
      exec "#{formula_opt_bin("node@24")}/node" "#{libexec}/mosaik.mjs" "$@"
    SH
  end

  test do
    assert_equal version.to_s, shell_output("#{bin}/mosaik --version").strip
  end
end
