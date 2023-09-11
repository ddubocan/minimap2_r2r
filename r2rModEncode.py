

# merge read-read alignment + with read-genome alignment 
# for base modifications

# iterate through genome aligned read + and then use read-read alignment index
# for fast random access via read name (won't work vice versa because chroms are indexed)

#check if MM/ML exists and update accordingly





# Overview
# Grab Reads
# Grab Aligned Pairs for Read2Read Alignment
# For Modified Base of interest [i.e. m6(A), m5(C)]:
#		Get forward positions of modified base
# 		Use get aligned pairs to convert into ref-read coordinates	
#		Convert into MM tag format



import pysam 
import sys
import numpy as np 
import gzip
import subprocess
import shlex
import argparse
import tqdm
from numba import jit

def inputArgs():
	'''Parse in arguments. '''
	
	parser = argparse.ArgumentParser()
	
	parser.add_argument('-m','--mods', 
		type = str, 
		help = 'read-2-read bam alignment with mods in MM/ML field')

	parser.add_argument('-r','--r2r', 
		type = str, 
		help = 'read-2-read bam alignment with mods in MM/ML field')

	parser.add_argument('-o','--output',
		type=str,
		default = 'aligned_reads.r2r_mods.bam',
		help = 'output bam name')

	parser.add_argument('-a','--alignment',
		type=str,
		help = 'ref-reads aligned to ref genome bam file')

	parser.add_argument('-b','--bases',
		type=str,
		help = 'modification base, options = [ A,C,G,T ]')

	parser.add_argument('-t','--threads',
		type=int,
		default = 1,
		help = 'Number of threads to use for reading input +  output sorting, indexing')

	args = parser.parse_args()

	return args.mods, args.r2r, args.output, args.alignment, args.bases, args.threads

def coordinateConversion_MMTag(sequence, base, modification_coords):
	'''Sequence is array of bases. Base is a base 
		for conversion to the coordinate system 
		used in the MM tag.'''

	mask = sequence == bytes(base, encoding='utf-8')
 	# find all masks = boolean Array 
	
	coords = modification_coords
	# coords = modification_coords[ sequence[modification_coords] == bytes(base, encoding='utf-8') ] 
	
	# when working with double stranded data we can only use modifications
	# on the specifc base that the modification would fall on on that strand
	# i.e. As  on + , Ts on -, we only want the mods that = that base of interest

	MM_coords = ','.join(list((np.diff(np.cumsum(mask)[coords]) - 1).astype(str)))

	return MM_coords 

# @jit(fastmath=True)
# def getR2RInfo(aligned_pairs,forward_mods):

# 	positions = []
# 	for i in range(len(aligned_pairs[0])):
# 		if aligned_pairs[0][i] in forward_mods[0]:
# 			positions.append(aligned_pairs[1][i])


# 	quals = []

# 	for i in range(len(forward_mods[0])):
# 		if forward_mods[0][i] in aligned_pairs[0]:
# 			quals.append(forward_mods[1][i])

# 	# idx = np.isin(aligned_pairs[0],forward_mods[0])

# 	# positions = aligned_pairs[1][idx].astype(int) # new positions from sup model

# 	# quals = forward_mods[1][np.isin(forward_mods[0],aligned_pairs[0])].astype(int)

# 	return positions, quals



def processAlignments(r2r_bam, alignment_bam, output_bam, read2mods, base):


	for ref_read in tqdm.tqdm(alignment_bam):
		
		for r2r_read in r2r_bam.fetch(ref_read.query_name):
			
			if not r2r_read.is_secondary and not r2r_read.is_secondary:
				

				if r2r_read.query_name not in read2mods:
					continue
				

				mods = read2mods[r2r_read.query_name]
				
				for m in mods:
					if m[0] == base:
						forward_mods = mods[m]

				forward_mods = np.vstack(forward_mods).T #0th is position, 1th is quality

				aligned_pairs = np.vstack(r2r_read.get_aligned_pairs(with_seq=False,matches_only=True)).T.astype(int) #0th is read, 1th is ref_read, 2nd is ref base


				idx = np.isin(aligned_pairs[0],forward_mods[0])

				positions = aligned_pairs[1][idx].astype(int) # new positions from sup model

				quals = forward_mods[1][np.isin(forward_mods[0],aligned_pairs[0])].astype(int)

				# positions,quals = getR2RInfo(aligned_pairs,forward_mods)


				# positions and quals is now what we want to encode in the aligned bam output

				# need to artificially encode the first base in the ref-forwrd-sequence in order
				# for the beginning offset to make sense + maintain length with the quals arr
				# this is because the MM tag is generated by np.diff. So length of MM is len(arr) - 1


				forseq = ref_read.get_forward_sequence()

				first_occurence = forseq.index(base)

				adjust_positions = np.insert(positions,0,first_occurence) 
				# need to get the position of the first T because everything is offset from there 
				# when calculating MM tag
				
				forward_sequence = sequence = np.frombuffer(bytes(forseq, "utf-8"), dtype="S1")

				MM_coords = coordinateConversion_MMTag(forward_sequence,base,adjust_positions)
				MM_tag = "A+a," + MM_coords
				ML_tag = [int(ml) for ml in list(quals)]

				ref_read.set_tag("MM", MM_tag, replace=True)
				ref_read.set_tag("ML", ML_tag, replace=True)
				output_bam.write(ref_read)


def readMods(bam):

	# generate dictionary of read_id to mods 

	read2mod_dict = {}
	count = 0 
	for read in tqdm.tqdm(bam):
		
		#count +=1
		#if count > 500:
		#	break
		read2mod_dict[read.query_name] = read.modified_bases_forward


	return read2mod_dict

def main():

	#get input args
	mods, r2r, output, alignment, base, threads = inputArgs()


	alignment_bam = pysam.AlignmentFile(alignment,'rb', threads = threads) 
	header = alignment_bam.header.to_dict()

	output_bam = pysam.AlignmentFile(output, "wb", header = header, threads = threads)

	mod_bam = pysam.AlignmentFile(mods,'rb', threads = threads, check_sq=False) 

	r2r_bam = pysam.AlignmentFile(r2r,'rb',threads=threads)

	read2mods = readMods(mod_bam)

	processAlignments(r2r_bam, alignment_bam, output_bam, read2mods, base)




	
if __name__=="__main__":
	main()

