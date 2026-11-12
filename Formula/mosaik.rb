class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/rehearsal-v2.0.0-43210155220-1/mosaik-2.0.0.tar.gz"
  sha256 "59ffb89bd9be59571f60954f5e3b863493cf9b7a01e014e54d9993f71b5e68c3"
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
