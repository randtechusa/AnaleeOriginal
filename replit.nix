{pkgs}: {
  deps = [
    pkgs.postgresql
    pkgs.openssl
    pkgs.glibcLocales
  ];
}