import React, { useRef, useEffect, useState } from 'react'
import { Box, Paper } from '@mui/material'

interface RegionOfInterestProps {
  imageUrl: string
  initialRegion?: number[]
  onChange: (region: number[]) => void
}

const RegionOfInterest: React.FC<RegionOfInterestProps> = ({
  imageUrl,
  initialRegion = [0, 0, 100, 100],
  onChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null)
  const [currentRegion, setCurrentRegion] = useState(initialRegion)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = new Image()
    img.src = imageUrl
    img.onload = () => {
      canvas.width = img.width
      canvas.height = img.height
      ctx.drawImage(img, 0, 0)
      drawRegion(currentRegion)
    }
  }, [imageUrl])

  const drawRegion = (region: number[]) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const img = new Image()
    img.src = imageUrl
    img.onload = () => {
      ctx.drawImage(img, 0, 0)
      ctx.strokeStyle = 'red'
      ctx.lineWidth = 2
      ctx.strokeRect(region[0], region[1], region[2] - region[0], region[3] - region[1])
    }
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setIsDrawing(true)
    setStartPoint({ x, y })
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    const newRegion = [
      Math.min(startPoint.x, x),
      Math.min(startPoint.y, y),
      Math.max(startPoint.x, x),
      Math.max(startPoint.y, y),
    ]

    setCurrentRegion(newRegion)
    drawRegion(newRegion)
  }

  const handleMouseUp = () => {
    if (!isDrawing || !startPoint) return

    setIsDrawing(false)
    onChange(currentRegion)
  }

  return (
    <Paper elevation={3} sx={{ p: 2 }}>
      <Box sx={{ position: 'relative' }}>
        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          style={{ border: '1px solid #ccc' }}
        />
      </Box>
    </Paper>
  )
}

export default RegionOfInterest
