import random

from dungeon_generator.cell import Cell
from dungeon_generator.celltype import EmptyCell, FloorCell
from dungeon_generator.region import Region
from dungeon_generator.room import Room


class Maze:
    ROOM_TRIES = 500
    DISCARD_ADJACENT_CHANCE = 10
    RANDOM_CONNECTOR_CHANCE = 100
    WINDING_PERCENT = 20

    _regions = []  # will only be used for generation
    _rooms = []
    _corridors = []
    grid = None  # will store a 2D array

    def __init__(self, width, height):
        if width % 2 == 0 or height % 2 == 0:
            raise ValueError("Maze height and width must be odd.")
        self.width = width
        self.height = height
        self.grid = [
            [Cell(x, y, maze=self, cell_type=EmptyCell.key)
             for y in range(height)]
            for x in range(width)
        ]
        self.RANDOM_CONNECTOR_CHANCE = int(width * height / 10)
        self.connection_root = None

    def __str__(self):
        ret = '='.join(['' for _ in range(0, self.width + 5)]) + '\n'
        for y in reversed(range(self.height)):
            line = '|{} '.format(y % 10)
            for x in range(self.width):
                line += str(self.grid[x][y])
            ret += line + ' |\n'
        ret += '='.join(['' for _ in range(0, self.width + 5)])
        return ret

    def __getitem__(self, item):
        if not isinstance(item, int):
            raise ValueError("Index must be an integer.")
        return self.grid[item]

    def cells(self):
        for x in range(0, self.width):
            for y in range(0, self.height):
                yield self[x][y]

    def generate(self):
        if not (
            self._generate_rooms() and
            self._flood() and
            self._connect() and
            self._clean()
        ):
            return False
        return True

    def _get_region_of_cell(self, cell):
        for region in self._regions:
            if cell in region.cells:
                return region
        return None

    def _carve(self, pos=None, cell=None, force=False, cell_type=FloorCell):
        if not cell:
            if not pos:
                raise ValueError("Either cell or position tuple must be given.")
            cell = self.grid[pos[0]][pos[1]]
        if not force and not cell.is_carveable():
            raise ValueError("{} is not carveable.".format(repr(cell)))
        cell.cell_type = cell_type
        return cell

    def _uncarve(self, pos=None, cell=None):
        if not cell:
            if not pos:
                raise ValueError("Either cell or position tuple must be given.")
            cell = self.grid[pos[0]][pos[1]]
        cell.cell_type = EmptyCell
        return cell

    def _generate_rooms(self):
        print("Generating rooms...")
        self._rooms = []
        for i in range(Maze.ROOM_TRIES):
            pos_x = random.randrange(3, self.width - Room.MAX_WIDTH - 2, step=2)
            pos_y = random.randrange(3, self.height - Room.MAX_HEIGHT - 2, step=2)
            width = random.randrange(Room.MIN_WIDTH, Room.MAX_WIDTH, step=2)
            height = random.randrange(Room.MIN_HEIGHT, Room.MAX_HEIGHT, step=2)

            new_room = Room(pos_x, pos_y, width, height)
            for room in self._rooms:
                if new_room.overlaps(room):  # or new_room.is_adjacent_to(room=room):
                    break
            else:
                self._rooms.append(new_room)

        for room in self._rooms:
            region = Region()
            for x in range(room.pos_x, room.pos_x + room.width):
                for y in range(room.pos_y, room.pos_y + room.height):
                    cell = self._carve(pos=(x, y), force=True)
                    region += cell
            self._regions.append(region)

        print('{} rooms generated.'.format(len(self._rooms)))
        return True

    def _flood(self):
        print("Generating corridors...")
        for x in range(self.width):
            for y in range(self.height):
                origin = self.grid[x][y]
                if origin.cell_type != EmptyCell or not origin.is_carveable():
                    continue

                region = Region()
                region += self._carve(cell=origin)

                valid_cells = [origin]
                while len(valid_cells) != 0:
                    # always pick the last carved cell
                    # cell = valid_cells[-1]
                    # OR
                    # pick at random
                    cell = random.choice(valid_cells)
                    # OR
                    # pick at random, weighted towards latest
                    # todo

                    to_carve = None

                    # try to move right ahead (1 - Maze.WINDING_PERCENT) of the time
                    if random.randrange(100) > Maze.WINDING_PERCENT:
                        if len(valid_cells) > 2 and len(cell.neighbors(carveable=True)) == 1:
                            prev = cell.neighbors(carveable=True)[0]
                            prev_dir = prev.direction_towards(cell)
                            to_carve = getattr(cell, prev_dir)(carveable=True)

                    if not to_carve:
                        carveable_neighbors = cell.neighbors(carveable=True)
                        if carveable_neighbors:
                            to_carve = random.choice(carveable_neighbors)
                        else:
                            valid_cells.remove(cell)
                            continue

                    carved_cell = self._carve(cell=to_carve)
                    region += carved_cell
                    self._corridors.append(carved_cell)
                    valid_cells.append(carved_cell)
                self._regions.append(region)
        print("{} corridor tiles carved.".format(len(self._corridors)))
        return True

    def _connect(self):
        def finished():
            for i in range(1, len(self._rooms)):
                if i not in regions_merged:
                    return False
            return True

        regions_merged = set()

        self.connection_root = random.choice(self._rooms)
        region = self._get_region_of_cell(
            self.grid[self.connection_root.pos_x][self.connection_root.pos_y]
        )
        regions_merged.add(region.id)

        print("{} regions to connect.".format(len(self._regions)))
        print("Starting with region {}...".format(region.id))

        while not finished():
            around = region.around(connecting=True)

            while True:
                cell = random.choice(around)

                connected_cell_neighbors = cell.neighbors(cell_type=FloorCell)
                connected_cell = connected_cell_neighbors[0]
                if connected_cell in region.cells:
                    connected_cell = connected_cell_neighbors[1]
                other_region = self._get_region_of_cell(connected_cell)

                if other_region.id in regions_merged:
                    around.remove(cell)
                else:
                    carved = self._carve(cell=cell, force=True)
                    region += carved
                    regions_merged.add(other_region.id)
                    print("Region {} merged.\t\tMerged rooms: {}/{}".format(
                        str(other_region.id).zfill(3),
                        len([i for i in regions_merged if i <= len(self._rooms)]),
                        len(self._rooms)
                    ), end='\r')
                    for c in other_region.cells:
                        if c not in region.cells:
                            region += c
                            other_region -= c
                    break

        skip = False
        for cell in region.around():
            if skip:
                skip = False
                continue
            if random.randrange(self.RANDOM_CONNECTOR_CHANCE) == 0:
                self._carve(cell=cell, force=True)
                skip = True
        return True

    def _clean(self):
        print("Clearing map of dead ends...")
        for cell in self.cells():
            if cell.cell_type != EmptyCell and cell.is_edge():
                self._uncarve(cell=cell)

        while True:
            done = True
            for cell in self.cells():
                if (
                    cell.cell_type == EmptyCell or
                    len(cell.neighbors(cell_type=EmptyCell)) < 3
                ):
                    continue

                done = False
                self._uncarve(cell=cell)
            if done:
                return True
