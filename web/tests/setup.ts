import "@testing-library/jest-dom";

// O jsdom não implementa estas APIs do navegador; componentes como a busca (cmdk) e os menus usam.
if (typeof window !== "undefined") {
  window.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  Element.prototype.scrollIntoView ??= function () {};
}
