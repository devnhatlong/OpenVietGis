import {
  useCallback,
  useEffect
} from "react";
import {
  useBeforeUnload,
  useBlocker
} from "react-router-dom";

export const UNSAVED_NAVIGATION_MESSAGE =
  "Bản đồ có thay đổi chưa lưu. Nếu rời trang, các thay đổi cấu hình dùng chung sẽ bị mất.";

export function useUnsavedNavigationProtection(active: boolean) {
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      active &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search ||
        currentLocation.hash !== nextLocation.hash)
  );

  useBeforeUnload(
    useCallback(
      (event) => {
        if (!active) return;
        event.preventDefault();
        event.returnValue = "";
      },
      [active]
    )
  );

  useEffect(() => {
    if (!active && blocker.state === "blocked") {
      blocker.reset();
    }
  }, [active, blocker]);

  return blocker;
}
