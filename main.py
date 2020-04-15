import subprocess, os, argparse, GPUtil
if os.name == 'nt':
    import wexpect
else:
    import pexpect
from sgfmill import sgf
import pandas as pd
import progressbar as pb

b_player = ""
w_player = ""

def main():
    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    optional.add_argument("-p", "--playouts", help="set number of playouts; defaults to 1", default=1)
    optional.add_argument("-w", "--weights", help="indicate where the weights file is; defaults to elfv2 in the leela-zero-0.17 directory", default="elfv2")
    optional.add_argument("-o","--output", help="set the output CSV file; defaults to output_file.csv", default="output_file.csv")
    optional.add_argument("-e","--executable", help="set the executable Go AI program filename (must have GTP extension lz-analyze); defaults to leela-zero-0.17/leelaz", default="leelaz")

    required.add_argument("-s", "--sgf", help="indicate where the sgf file is", required=True)
    args = parser.parse_args()

    executable = args.executable
    playouts = args.playouts
    weights = args.weights
    sgf_file = args.sgf
    output_file = args.output

    # Generate Leela commands from SGF file
    communicate_string = generate_leela_commands(sgf_file)

    # Primary function - run majority of the code
    df = get_csv_output(executable, playouts, weights, communicate_string)

    # Output results to CSV
    df.to_csv(output_file,index=False)
    print("Success! File outputted to {}".format(output_file))

def generate_leela_commands(sgf_file):
    """Returns a formatted list of commands for insertion into the Leela CLI (communicate_string)"""

    with open(sgf_file, "rb") as f:
        game = sgf.Sgf_game.from_bytes(f.read())
    winner = game.get_winner()
    board_size = game.get_size()
    root_node = game.get_root()
    
    global b_player
    global w_player

    try:
        b_player = root_node.get("PB")
    except:
        b_player = "Unknown1"
    try:
        w_player = root_node.get("PW")
    except:
        w_player = "Unknown2"

    print("The Black player is: {}".format(b_player))
    print("The White player is: {}".format(w_player))
    print("The winner was: {}".format(winner))

    # Basic conversion function from numerical columns to lettered columns; have to exclude I
    let_num_convert = {'1':'a','2':'b','3':'c','4':'d','5':'e','6':'f','7':'g','8':'h','9':'j',
                   '10':'k','11':'l','12':'m','13':'n','14':'o','15':'p','16':'q','17':'r',
                   '18':'s','19':'t'}

    communicate_string = ""

    # Debugging list so that there's always a list of human moves sent to Leela to actually play on the board
    basic_moves = []
    
    # The first element is excluded because it is always [None, None], presumably signifying the beginning of a game
    for node in game.get_main_sequence()[1:]:

        # Get the current move - tuple consisting of ('color', [coordinate_1,coordinate_2])
        game_move = node.get_move()

        # When a player has passed, the second element of the tuple is None. In this case, I just skip to the next iteration
        if game_move[1] == None:
            continue
        
        # Use dictionary to convert numeric x coordinate to letter
        x_coord = let_num_convert[str(game_move[1][1] + 1)]
        
        # Generate the current move in the format that Leela Zero wants
        cur_move = x_coord + str(game_move[1][0] + 1)

        # Ask Leela Zero to find the moves it likes the most, maximum 10 moves. Forbid Leela Zero from analyzing Pass and Resign as valid moves.
        # Does not actually place a move on the board
        computers_move = 'lz-analyze 100 avoid {} pass,resign 1'.format(game_move[0])

        # Prepare a backup command (which may not be run) to find the stats for the human's prospective move (V/N/LCB) if Leela Zero did not originally
        # have it as one of its options. Does not actually place a move on the board
        humans_move = 'lz-analyze 100 allow {} __ 1 avoid {} pass,resign 1'.format(game_move[0],game_move[0])
        
        # Once all analysis is complete for a given move, actually play the human's move on the board.
        actually_play_move = 'play {} {}'.format(game_move[0],cur_move)

        basic_moves.append(actually_play_move)
        
        # Update communicate_string to include the latest commands
        communicate_string = "\n".join([communicate_string,computers_move,humans_move,actually_play_move])

    # Eliminate empty string
    communicate_string = communicate_string[1:]

    return communicate_string

def extract_top_10_moves(before_text):
    """Converts the raw string stderr from Leela Zero into a more functional list of dictionaries"""

    top_10_moves = []
    for possible_move_string in before_text:
        v_value = possible_move_string.split("(V: ")[1].split("%")[0]
        n_value = possible_move_string.split("(N: ")[1].split("%")[0]
        lcb_value = possible_move_string.split("(LCB: ")[1].split("%")[0]
        move_coord = possible_move_string.split("->")[0].strip().lower()
        top_10_moves.append({'v_value': float(v_value),'n_value': float(n_value),'lcb_value':float(lcb_value),'move_coord':move_coord})
    return top_10_moves

def get_csv_output(executable, playouts, weights, communicate_string):
    """Primary function - first three parameters build the basic setup command, the latter two are used to run the CLI and generate the output CSV"""

    # Extra argument to add at the end
    final_args = "--noponder"

    # If the machine is Linux-based, add the folders to the paths; if it is Windows, just change the current working directory
    if os.name == 'posix':
        executable = "./leela-zero-0.17/" + executable
        weights = "./leela-zero-0.17/" + weights
    else:
        os.chdir('./leela-zero-0.17')

    # Check if the user's computer has one or more GPUs - if not, set it to only use CPUs
    if not GPUtil.getGPUs():
        final_args += " --cpu-only"

    # Key command - configure the actual Leela Zero run string and print it out on-screen for ease of testing
    run_string = "{} -g -r 0 -d -p {} -w {} {}".format(executable, playouts, weights, final_args)
    print(run_string)

    # On Windows, use wexpect, on Linux, use pexpect. Slightly different commands for each to begin Leela Zero
    if os.name == 'nt':
        child = wexpect.spawn('cmd.exe')
        child.expect('>', timeout=120)
        child.sendline(run_string)
    else:
        child = pexpect.spawn('/bin/bash -c "{}"'.format(run_string))
    child.expect('Setting max tree', timeout=120)
    
    # Once Leela Zero is loaded, we definitely want these three commands run first and foremost
    starting_commands = ["boardsize 19","clear_board","komi 7.5"]
    for command in starting_commands:
        child.sendline(command)
        child.expect('=', timeout=120) # Basic Leela Zero commands always end with a '=' on success (not including lz-analyze)

    # Convert our giant string of commands into a list of commands
    communicate_string_list = communicate_string.split("\n")

    # Output the full communicate_string to command_log.log for further debug review as desired
    with open("command_log.log","w") as my_file:
        my_file.write("\n".join(communicate_string_list))

    # Set a basic counter for the current move number
    y = 0

    # all_moves will eventually become our final dataframe
    all_moves = []

    # Initiate the progress bar
    bar = pb.ProgressBar()
    colors = ['white','black']

    # At long last, execute our strings line-by-line. Do it three-by-three since each move has three associated commands (2x 'lz-analyze' plus 'play')
    for x in bar(range(0,len(communicate_string_list),3)):
        y += 1
        # If the game is going longer than 180 moves, we can exit Leela Zero
        if y == 181:
            break

        # Extract the human's move from the 'play <color> <coordinate>' command
        human_move = communicate_string_list[x+2].split(" ")[2]

        # Send the primary lz-analyze command to Leela Zero; 'max depth' appears at the end of Leela Zero's output
        child.sendline(communicate_string_list[x])
        child.expect(" max depth", timeout=120)

        # Only extract those lines of text that have actual moves in them with the key '->' substring.
        # Windows can just split it immediately, but Linux machines require the string to be decoded first.
        if os.name == 'nt':
            before_text = [line.strip() for line in child.before.split("\n") if "->" in line]
        else:
            before_text = [line.strip() for line in child.before.decode("utf-8").split("\n") if "->" in line]
        
        # The first line will be the move with the highest LCB winrate, which is what Leela thinks is the "best" option
        ai_first_choice_move = before_text[0]
        
        # Extract move coordinates and other values from the line of text
        ai_move_coords = ai_first_choice_move.split("->")[0].strip().lower()
        ai_v_value = ai_first_choice_move.split("(V: ")[1].split("%")[0]
        ai_n_value = ai_first_choice_move.split("(N: ")[1].split("%")[0]
        ai_lcb_value = ai_first_choice_move.split("(LCB: ")[1].split("%")[0]
        
        global b_player
        global w_player
        
        if colors[y%2] == 'black':
            player = b_player
        else:
            player = w_player
        # Begin construction of move_info, i.e. one row of data in our output spreadsheet
        move_info = {'move_number':y,'ai_move':ai_move_coords,'ai_v_value':ai_v_value,
                   'ai_n_value':ai_n_value,'ai_lcb_value':ai_lcb_value, 'human_move':human_move, 'color':colors[y%2], 'player':player}
        
        # As a default, assume the human's move was NOT one of the those identified by Leela Zero. Also extract all 10 moves into a pretty list.
        is_match_found = False
        top_10_moves = extract_top_10_moves(before_text)

        # Go through each move that Leela Zero looked at, checking if any were the human's move. If so, update move_info accordingly
        for top_10_move in top_10_moves:
            if top_10_move['move_coord'] == human_move:
                move_info['is_requery_needed'] = 0
                move_info['human_v_value'] = top_10_move['v_value']
                move_info['human_n_value'] = top_10_move['n_value']
                move_info['human_lcb_value'] = top_10_move['lcb_value']
                is_match_found = True
                break
                
        # However, if the human's move is NOT found among the top moves that Leela Zero looked at...
        if not is_match_found:
            human_command = communicate_string_list[x+1]

            # Still setting is_requery_needed to zero - only set to 1 if this second attempt fails
            move_info['is_requery_needed'] = 0

            # Sort the top 10 moves in ascending order by n_value. Then generate a list of allowed_moves containing the human's move and the
            # other 9 Leela Zero moves that didn't have the lowest n-value.
            sorted_top_10 = sorted(top_10_moves, key = lambda i: i['n_value'])
            allowed_moves = human_move
            lowest_n = sorted_top_10[0]['n_value'] # Save this value for possible use later
            for top_10_move in sorted_top_10[2:]:
                allowed_moves += "," + top_10_move['move_coord']

            # Replace the "__" placeholder in this command with our new list - this will (theoretically) ensure that Leela gives the move proper attention
            human_command = human_command.replace("__",allowed_moves)
            child.sendline(human_command)
            child.expect(" max depth", timeout=120)

            # Same as before - eventually I should abstract this into a single function since I'm doing the same thing twice
            if os.name == 'nt':
                before_text = [line.strip() for line in child.before.split("\n") if "->" in line]
            else:
                before_text = [line.strip() for line in child.before.decode("utf-8").split("\n") if "->" in line]
            top_10_moves = extract_top_10_moves(before_text)

            is_match_found = False

            # So in theory, it should always have the move now. However, it doesn't *always* (about 95% of the time it does). 
            # You'd know better than me precisely why.
            for top_10_move in top_10_moves:
                if top_10_move['move_coord'] == human_move:
                    move_info['human_v_value'] = top_10_move['v_value']
                    move_info['human_n_value'] = top_10_move['n_value']
                    move_info['human_lcb_value'] = top_10_move['lcb_value']
                    is_match_found = True
                    break
                    
            # Finally, we're now going for absolutely *force* Leela Zero to give us the V and LCB values by re-running the previous command
            # but with only a single allowable move on the entire board - the move want it to.
            # The downside, however, is that the N value is lost. Since only one move is allowable, the N value becomes about 99.96% or so.
            # To mitigate this, I just give this human move an n-value equal to the lowest N-value from the top 10 moves Leela Zero considered.
            # This is admittedly not an ideal solution, open to better ideas?
            if not is_match_found:
                human_command = human_command.replace(allowed_moves,human_move)
                child.sendline(human_command)
                child.expect(" max depth", timeout=120)
                before_text = [line.strip() for line in child.before.split("\n") if "->" in line]
                top_10_moves = extract_top_10_moves(before_text)
                move_info['human_v_value'] = top_10_moves[0]['v_value']
                move_info['human_n_value'] = lowest_n
                move_info['human_lcb_value'] = top_10_moves[0]['lcb_value']
                move_info['is_requery_needed'] = 1

        # Add the "row" of data to the all_moves list
        all_moves.append(move_info)
        
        # Execute the 3rd command - very simple, just play the human's move on the board
        child.sendline(communicate_string_list[x+2])
        child.expect('=', timeout=120)
    child.sendline('exit')

    # Generate the dataframe, organize the columns, and return the finished dataframe
    df = pd.DataFrame(all_moves)
    column_order = ["move_number","color","human_move","ai_move","human_v_value","ai_v_value","human_n_value","ai_n_value","human_lcb_value","ai_lcb_value",'is_requery_needed','player']
    df = df[column_order]
    return df

if __name__ == "__main__":
    main()
