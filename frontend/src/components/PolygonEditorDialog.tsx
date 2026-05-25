import React, { useEffect, useRef, useState } from 'react'
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Tooltip, Typography } from '@mui/material'
import { Delete as ClearIcon, Undo as UndoIcon } from '@mui/icons-material'

interface Props {
  open: boolean
  title?: string
  imageUrl: string
  initialPolygon?: [number, number][]
  onSave: (polygon: [number, number][]) => void
  onCancel: () => void
}

/** Normalized point [x, y] in range 0–1 relative to canvas dimensions. */
type NPoint = [number, number]

const CLOSED_MIN = 3

export const PolygonEditorDialog: React.FC<Props> = ({
  open,
  title = 'Draw Zone',
  imageUrl,
  initialPolygon,
  onSave,
  onCancel,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [points, setPoints] = useState<NPoint[]>(initialPolygon ?? [])
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState(false)

  // Reset when dialog opens
  useEffect(() => {
    if (open) {
      setPoints(initialPolygon ?? [])
      setImgLoaded(false)
      setImgError(false)
    }
  }, [open, imageUrl])

  // Load image
  useEffect(() => {
    if (!open) return
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imgRef.current = img
      setImgLoaded(true)
    }
    img.onerror = () => setImgError(true)
    img.src = imageUrl
  }, [open, imageUrl])

  // Redraw whenever points or image changes
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Background
    if (imgRef.current && imgLoaded) {
      ctx.drawImage(imgRef.current, 0, 0, canvas.width, canvas.height)
    } else {
      ctx.fillStyle = '#111'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      if (!imgError) {
        ctx.fillStyle = '#888'
        ctx.font = '14px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('Loading preview…', canvas.width / 2, canvas.height / 2)
      } else {
        ctx.fillStyle = '#888'
        ctx.font = '14px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('No preview available — draw zone on blank frame', canvas.width / 2, canvas.height / 2)
      }
    }

    if (points.length === 0) return

    const toCanvas = (p: NPoint): [number, number] => [p[0] * canvas.width, p[1] * canvas.height]

    // Draw filled polygon when closed
    if (points.length >= CLOSED_MIN) {
      ctx.beginPath()
      const [fx, fy] = toCanvas(points[0])
      ctx.moveTo(fx, fy)
      for (let i = 1; i < points.length; i++) {
        const [cx, cy] = toCanvas(points[i])
        ctx.lineTo(cx, cy)
      }
      ctx.closePath()
      ctx.fillStyle = 'rgba(33, 150, 243, 0.25)'
      ctx.fill()
      ctx.strokeStyle = 'rgba(33, 150, 243, 0.9)'
      ctx.lineWidth = 2
      ctx.stroke()
    } else {
      // Just draw the open line
      ctx.beginPath()
      const [fx, fy] = toCanvas(points[0])
      ctx.moveTo(fx, fy)
      for (let i = 1; i < points.length; i++) {
        const [cx, cy] = toCanvas(points[i])
        ctx.lineTo(cx, cy)
      }
      ctx.strokeStyle = 'rgba(33, 150, 243, 0.9)'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Draw vertex dots
    points.forEach(([nx, ny], idx) => {
      const [cx, cy] = toCanvas([nx, ny])
      ctx.beginPath()
      ctx.arc(cx, cy, idx === 0 ? 7 : 5, 0, Math.PI * 2)
      ctx.fillStyle = idx === 0 ? '#FF5722' : '#2196F3'
      ctx.fill()
      ctx.strokeStyle = 'white'
      ctx.lineWidth = 1.5
      ctx.stroke()
    })
  }, [points, imgLoaded, imgError])

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const nx = (e.clientX - rect.left) / rect.width
    const ny = (e.clientY - rect.top) / rect.height
    setPoints((prev) => [...prev, [nx, ny]])
  }

  const handleUndo = () => setPoints((prev) => prev.slice(0, -1))
  const handleClear = () => setPoints([])

  const canSave = points.length >= CLOSED_MIN

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent sx={{ pb: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Click on the image to place vertices. A polygon requires at least {CLOSED_MIN} points. The first vertex is
          shown in orange.
        </Typography>
        <Box sx={{ position: 'relative', bgcolor: '#000', borderRadius: 1, overflow: 'hidden' }}>
          <canvas
            ref={canvasRef}
            width={800}
            height={450}
            style={{ width: '100%', height: 'auto', display: 'block', cursor: 'crosshair' }}
            onClick={handleCanvasClick}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1, mt: 1, alignItems: 'center' }}>
          <Tooltip title="Remove last point.">
            <span>
              <Button size="small" startIcon={<UndoIcon />} onClick={handleUndo} disabled={points.length === 0}>
                Undo
              </Button>
            </span>
          </Tooltip>
          <Tooltip title="Clear all points.">
            <span>
              <Button
                size="small"
                startIcon={<ClearIcon />}
                onClick={handleClear}
                color="error"
                disabled={points.length === 0}
              >
                Clear
              </Button>
            </span>
          </Tooltip>
          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
            {points.length} point{points.length !== 1 ? 's' : ''}
            {points.length >= CLOSED_MIN ? ' — polygon ready' : ` — need ${CLOSED_MIN - points.length} more`}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="contained" onClick={() => onSave(points)} disabled={!canSave}>
          Save Zone
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default PolygonEditorDialog
