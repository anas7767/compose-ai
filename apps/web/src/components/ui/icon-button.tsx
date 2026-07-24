import * as React from "react";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";

interface IconButtonProps extends React.ComponentProps<typeof Button> {
  label: string;
  tooltip?: string;
}

function IconButton({ label, size = "icon", tooltip = label, ...props }: IconButtonProps) {
  return (
    <Tooltip content={tooltip}>
      <Button aria-label={label} size={size} {...props} />
    </Tooltip>
  );
}

export { IconButton };
