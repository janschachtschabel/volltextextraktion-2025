#+title: text-extraction-smart
#+EXPORT_EXCLUDE_TAGS: noexport

A comprehensive, production-ready text extraction API that provides robust content extraction from URLs with advanced features for handling modern web challenges.

This is a clean, minimal, and effective implementation that addresses all historical problems while incorporating comprehensive improvements including JavaScript/SPA support, file conversion, proxy rotation, link extraction, and quality metrics.

* Usage as service

With ~Nix~, no further installation is required to run the micro-service. Simply run the following command:
#+begin_src shell
nix run github:openeduhub/text-extraction
#+end_src

If the package has been installed locally, the service is available as ~text-extraction~ from the command line.

Once started, see the ~Swagger~ UI for documentation on the service. It is located on =http://localhost:8080/docs= by default.

* Usage as library

For more customization and control over behavior, use the implemented functionality as a native Python library, instead of the provided REST API.

The functions that should be of primary interest are ~from_headless_browser_unlimited~ and ~from_html_unlimited~, found in the ~text_extraction.grab_content~ module.

Rate-limiting can be set up using the ~text_extraction.rate_limiting~ module, e.g.
#+begin_src python
from text_extraction.grab_content import from_headless_browser_unlimited
from text_extraction.rate_limiting import get_simple_multibucket_limiter, domain_mapper

# limit per-domain accesses to 5 per second and 50 per minute
limiter = get_simple_multibucket_limiter(
    max_rate_per_second=5, base_weight=1
).as_decorator()(domain_mapper)

from_headless_browser_limited = limiter(from_headless_browser_unlimited)
#+end_src

#+RESULTS:
: None

* Installation
** Through Nix

Add this repository to your Flake inputs. This may look like this:
#+begin_src nix
{
  inputs = {
    text-extraction = {
      url = "github:openeduhub/texte-extraction";
      # optional if using as service, required if using as library
      nixpkgs.follows = "nixpkgs"; 
    };
  };
}
#+end_src

The micro-service is provided both as a ~nixpkgs~ overlay and as an output (~packages.${system}.text-extraction~). Thus, it may be included through
#+begin_src nix
{
  outputs = { self, nixpkgs, text-extraction, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ text-extraction.overlays.default ];
      };
    in
      { ... };
}
  
#+end_src

The Python library is provided as another ~nixpkgs~ overlay:
#+begin_src nix
{
  outputs = { self, nixpkgs, text-extraction, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ text-extraction.overlays.python-lib ];
      };
      
      python = pkgs.python3;
      python-with-packages = python.withPackages (py-pkgs: [
        # some example packages
        py-pkgs.numpy
        py-pkgs.pandas
        # the text-extraction library, used as any other python library
        py-pkgs.text-extraction
      ]);
    in
      { ... };
}
#+end_src

** Through Pip

The package, including both the micro-service and the Python library, can also be installed through ~pip~:
#+begin_src shell
pip install git+https://github.com/openeduhub/text-extraction.git
#+end_src

