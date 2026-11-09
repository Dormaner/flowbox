import { createContext } from 'react'

/** 悬停某张卡片时，只留它的入线/出线，其余线淡掉（Blender 的做法） */
export const HoverCtx = createContext<{
  hover: string | null
  setHover: (id: string | null) => void
}>({ hover: null, setHover: () => {} })
