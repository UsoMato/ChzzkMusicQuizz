import { useState, useEffect } from 'react';
import './ImageReveal.css';

interface ImageRevealProps {
    src: string;
    gridSize?: number; // default 8 (8x8 = 64 tiles)
}

const ImageReveal = ({ src, gridSize = 5 }: ImageRevealProps) => {
    const totalTiles = gridSize * gridSize;
    const [removedIndices, setRemovedIndices] = useState<Set<number>>(new Set());

    // Reset revealed tiles when image source changes
    useEffect(() => {
        setRemovedIndices(new Set());
    }, [src]);

    const handleTileClick = (e: React.MouseEvent, index: number) => {
        e.stopPropagation(); // Stop event from bubbling up to parent (which might toggle play)

        // Only process if not already removed
        if (!removedIndices.has(index)) {
            const newRemoved = new Set(removedIndices);
            newRemoved.add(index);
            setRemovedIndices(newRemoved);
        }
    };

    return (
        <div className="image-reveal-container">
            <img
                src={src}
                alt="Question"
                style={{
                    display: 'block',
                    maxHeight: '300px',
                    maxWidth: '100%',
                    width: 'auto',
                    height: 'auto',
                    objectFit: 'contain'
                }}
            />

            <div className="tile-grid" style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                display: 'grid',
                gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
                gridTemplateRows: `repeat(${gridSize}, 1fr)`
            }}>
                {Array.from({ length: totalTiles }).map((_, i) => (
                    <div
                        key={i}
                        className={`tile ${removedIndices.has(i) ? 'removed' : ''}`}
                        onClick={(e) => handleTileClick(e, i)}
                    />
                ))}
            </div>
        </div>
    );
};

export default ImageReveal;
