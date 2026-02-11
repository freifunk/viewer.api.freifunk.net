{ pkgs, ... }:

{
  languages.python = {
    enable = true;
    version = "3.13.12";
  };

  packages = with pkgs; [
    python313Packages.jinja2
    python313Packages.requests
    python313Packages.packaging
    python313Packages.jsonschema
    python313Packages.progressbar33
    python313Packages.python-dateutil
  ];
}
