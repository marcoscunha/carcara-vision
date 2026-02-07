import React from 'react'
import { Grid as MuiGrid, GridProps } from '@mui/material'

export const Grid: React.FC<GridProps> = (props) => {
  return <MuiGrid {...props} />
}

export default Grid
