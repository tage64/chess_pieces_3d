import cadquery as cq

chess_piece_magnet = cq.Solid.makeCylinder(radius=3.1, height=6, pnt=(0, 0, 0.6), dir=(0, 0, 1))
