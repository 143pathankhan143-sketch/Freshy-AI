declare namespace React {
  interface FC<P = Record<string, never>> {
    (props: P): JSX.Element | null;
  }
  interface FormEvent<T = Element> {
    preventDefault(): void;
    currentTarget: T;
    target: EventTarget | null;
  }
  interface MutableRefObject<T> {
    current: T;
  }
  function useState<T>(initial: T | (() => T)): [T, (value: T | ((previous: T) => T)) => void];
  function useEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  function useRef<T>(initial: T): MutableRefObject<T>;
  function useCallback<T extends (...args: any[]) => any>(callback: T, deps: readonly unknown[]): T;
  function useMemo<T>(factory: () => T, deps: readonly unknown[]): T;
  const StrictMode: FC<{ children?: unknown }>;
}

declare module "react" {
  export = React;
}

declare module "react/jsx-runtime" {
  export const Fragment: unknown;
  export function jsx(type: unknown, props: unknown, key?: unknown): JSX.Element;
  export function jsxs(type: unknown, props: unknown, key?: unknown): JSX.Element;
}

declare module "react-dom/client" {
  export function createRoot(container: Element | DocumentFragment): {
    render(children: unknown): void;
  };
}

declare namespace JSX {
  interface Element {}
  interface IntrinsicElements {
    [elementName: string]: any;
  }
}
